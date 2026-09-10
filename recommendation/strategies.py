"""
Pluggable fit-check strategies used by BoxRecommendationService.

Kept separate from services.py so each check is independently testable
and so new strategies (e.g. a real 3D packer, later) can be swapped in
without touching the orchestration logic in services.py.
"""

from decimal import Decimal
from typing import List

from django.conf import settings

from recommendation.dto import BoxCandidate, OrderLine

# Documented assumption: fraction of a box's raw internal volume that is
# realistically usable once packing material, irregular shapes, and dead
# space are accounted for. Configurable via Django settings so it can be
# tuned/tested without touching code.
DEFAULT_PACKING_EFFICIENCY = Decimal("0.85")

# Documented assumption: once total volume used crosses this fraction of
# the *usable* (efficiency-adjusted) volume, we flag the recommendation
# as "tight" rather than "comfortable" so the warehouse team knows to
# double-check by hand rather than trusting it blindly.
DEFAULT_TIGHT_FIT_THRESHOLD = Decimal("0.75")


def get_packing_efficiency() -> Decimal:
    return Decimal(str(getattr(settings, "PACKING_EFFICIENCY_FACTOR", DEFAULT_PACKING_EFFICIENCY)))


def get_tight_fit_threshold() -> Decimal:
    return Decimal(str(getattr(settings, "TIGHT_FIT_THRESHOLD", DEFAULT_TIGHT_FIT_THRESHOLD)))


def item_fits_in_box(line: OrderLine, box: BoxCandidate) -> bool:
    """Hard constraint: does this single product's footprint fit inside
    the box in *some* axis-aligned rotation? This must hold regardless
    of how many other items are also in the box."""
    return line.dimensions.fits_in(box.dimensions)


def all_items_fit_in_box(lines: List[OrderLine], box: BoxCandidate) -> bool:
    return all(item_fits_in_box(line, box) for line in lines)


def weight_fits_in_box(total_weight: Decimal, box: BoxCandidate) -> bool:
    return total_weight <= box.max_weight


def volume_fits_in_box(total_volume: Decimal, box: BoxCandidate) -> bool:
    usable_volume = box.internal_volume * get_packing_efficiency()
    return total_volume <= usable_volume


def compute_confidence(total_volume: Decimal, box: BoxCandidate) -> str:
    """Return 'tight' or 'comfortable' based on how much of the box's
    usable volume the order actually consumes. This does not change
    whether the box is a valid candidate — it's an extra signal for the
    warehouse team so a recommendation that is technically valid but
    right at the edge isn't treated with the same confidence as one
    with plenty of headroom (see plan Failure #2: false positives risk).
    """
    usable_volume = box.internal_volume * get_packing_efficiency()
    if usable_volume <= 0:
        return "tight"
    ratio = total_volume / usable_volume
    return "tight" if ratio > get_tight_fit_threshold() else "comfortable"


def is_valid_single_box_candidate(lines: List[OrderLine], box: BoxCandidate,
                                   total_weight: Decimal, total_volume: Decimal) -> bool:
    return (
        all_items_fit_in_box(lines, box)
        and weight_fits_in_box(total_weight, box)
        and volume_fits_in_box(total_volume, box)
    )


def any_item_fits_alone(line: OrderLine, boxes: List[BoxCandidate]) -> bool:
    """Used to distinguish ITEM_TOO_LARGE (nothing can ever hold this
    single unit) from a plain capacity shortfall across the whole order.
    """
    return any(item_fits_in_box(line, box) for box in boxes)
