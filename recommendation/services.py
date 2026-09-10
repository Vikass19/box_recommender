"""
BoxRecommendationService — the single place "can this order be boxed,
and how" logic lives (DRY: views, admin actions, or management commands
should all call this rather than re-implementing any part of it).

Deliberately framework-light: takes plain dataclasses (OrderLine,
BoxCandidate) rather than Django ORM objects directly, so it can be
unit tested without a database and reused outside of a request/response
cycle if needed.
"""

import logging
from decimal import Decimal, ROUND_CEILING
from typing import List

from common.exceptions import InvalidOrderError, NoSuitableBoxError, ReasonCode
from recommendation.dto import (
    BoxCandidate,
    MultiBoxRecommendation,
    OrderLine,
    SingleBoxRecommendation,
)
from recommendation import strategies

logger = logging.getLogger(__name__)


def _ceil_div(numerator: Decimal, denominator: Decimal) -> int:
    """Ceiling division for Decimals, returned as an int box count.
    Guards against a zero/negative denominator (shouldn't happen given
    model validators, but defensive here since this is a division)."""
    if denominator <= 0:
        raise NoSuitableBoxError(
            "Box has no usable capacity.",
            reason=ReasonCode.NO_BOXES_AVAILABLE,
        )
    result = (numerator / denominator).to_integral_value(rounding=ROUND_CEILING)
    return max(int(result), 1)


class BoxRecommendationService:
    def __init__(self, order_lines: List[OrderLine], boxes: List[BoxCandidate]):
        self.order_lines = order_lines
        self.boxes = boxes

    # -- public API ---------------------------------------------------

    def recommend(self):
        """Returns a SingleBoxRecommendation or MultiBoxRecommendation.
        Raises InvalidOrderError or NoSuitableBoxError on failure.
        """
        self._validate_order()

        if not self.boxes:
            logger.warning("Recommendation failed: no active boxes in catalog.")
            raise NoSuitableBoxError(
                "No boxes are available in the catalog.",
                reason=ReasonCode.NO_BOXES_AVAILABLE,
            )

        total_weight = self._total_weight()
        total_volume = self._total_volume()

        single = self._find_best_single_box(total_weight, total_volume)
        if single is not None:
            return single

        multi = self._find_best_multi_box(total_weight, total_volume)
        if multi is not None:
            return multi

        self._raise_definitive_failure()

    # -- internal steps -------------------------------------------------

    def _validate_order(self):
        if not self.order_lines:
            raise InvalidOrderError(
                "Order must contain at least one item.",
                reason=ReasonCode.EMPTY_ORDER,
            )
        for line in self.order_lines:
            if line.quantity <= 0:
                raise InvalidOrderError(
                    f"Quantity for product '{line.product_name}' must be positive.",
                    reason=ReasonCode.EMPTY_ORDER,
                    detail={"product_id": line.product_id},
                )

    def _total_weight(self) -> Decimal:
        return sum((line.line_weight for line in self.order_lines), Decimal("0"))

    def _total_volume(self) -> Decimal:
        return sum((line.line_volume for line in self.order_lines), Decimal("0"))

    def _find_best_single_box(self, total_weight, total_volume):
        candidates = [
            box
            for box in self.boxes
            if strategies.is_valid_single_box_candidate(
                self.order_lines, box, total_weight, total_volume
            )
        ]
        if not candidates:
            return None

        # Step 4: cheapest first; tie-break smallest internal volume,
        # then smallest box_id — deterministic, never arbitrary ordering.
        best = min(candidates, key=lambda b: (b.cost, b.internal_volume, b.box_id))
        confidence = strategies.compute_confidence(total_volume, best)
        logger.info(
            "Single-box recommendation: box_id=%s cost=%s confidence=%s",
            best.box_id, best.cost, confidence,
        )
        return SingleBoxRecommendation(
            box=best,
            confidence=confidence,
            total_weight=total_weight,
            total_volume=total_volume,
        )

    def _find_best_multi_box(self, total_weight, total_volume):
        """Same-box-type splitting fallback (see plan Failure #1).

        Only considers box types where EVERY individual order line fits
        (in some rotation) inside a single unit of that box type — we
        are not attempting to mix box types or split a single line's
        quantity across box types in v1.
        """
        options = []
        efficiency = strategies.get_packing_efficiency()

        for box in self.boxes:
            if not strategies.all_items_fit_in_box(self.order_lines, box):
                continue

            weight_boxes = _ceil_div(total_weight, box.max_weight)
            usable_volume = box.internal_volume * efficiency
            volume_boxes = _ceil_div(total_volume, usable_volume)
            boxes_needed = max(weight_boxes, volume_boxes, 1)
            total_cost = box.cost * boxes_needed

            options.append((total_cost, boxes_needed, box))

        if not options:
            return None

        total_cost, boxes_needed, box = min(
            options, key=lambda o: (o[0], o[1], o[2].box_id)
        )
        reason = (
            "No single box can hold the full order; recommending multiple "
            "units of the cheapest viable box type."
        )
        logger.info(
            "Multi-box recommendation: box_id=%s quantity=%s total_cost=%s",
            box.box_id, boxes_needed, total_cost,
        )
        return MultiBoxRecommendation(
            box=box,
            quantity=boxes_needed,
            total_cost=total_cost,
            reason=reason,
        )

    def _raise_definitive_failure(self):
        """Neither a single box nor a multi-box split worked. Distinguish
        ITEM_TOO_LARGE (some unit can never be boxed, ever) from a
        generic NO_BOXES_AVAILABLE (each item fits somewhere, but no
        single box type accommodates every line at once)."""
        for line in self.order_lines:
            if not strategies.any_item_fits_alone(line, self.boxes):
                logger.warning(
                    "Recommendation failed: product_id=%s exceeds all box dimensions.",
                    line.product_id,
                )
                raise NoSuitableBoxError(
                    f"Product '{line.product_name}' (id={line.product_id}) exceeds "
                    "all box dimensions in every rotation.",
                    reason=ReasonCode.ITEM_TOO_LARGE,
                    detail={"product_id": line.product_id},
                )

        logger.warning("Recommendation failed: no box type accommodates all order lines together.")
        raise NoSuitableBoxError(
            "No single box type can accommodate all items in this order together, "
            "and no viable multi-box split was found.",
            reason=ReasonCode.NO_BOXES_AVAILABLE,
        )
