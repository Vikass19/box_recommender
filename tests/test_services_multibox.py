from decimal import Decimal

from django.test import SimpleTestCase, override_settings

from common.exceptions import NoSuitableBoxError, ReasonCode
from recommendation.services import BoxRecommendationService
from tests.test_services_happy_path import make_box, make_line


@override_settings(PACKING_EFFICIENCY_FACTOR=0.85, TIGHT_FIT_THRESHOLD=0.75)
class MultiBoxTests(SimpleTestCase):
    # Edge case #15: bulk quantity of one product exceeds any single box
    # -> multi-box split, not a hard failure.
    def test_bulk_quantity_triggers_multi_box_split(self):
        line = make_line(l="10", w="10", h="10", weight="1", qty=20)  # volume 20*1000=20000
        box = make_box(l="20", w="20", h="20", max_weight="100", cost="8.00")  # usable vol 6800

        result = BoxRecommendationService([line], [box]).recommend()

        self.assertEqual(result.recommendation_type, "multi_box")
        self.assertEqual(result.box.box_id, box.box_id)
        self.assertEqual(result.total_cost, box.cost * result.quantity)

    def test_cheapest_multi_box_option_chosen_across_box_types(self):
        # Large enough quantity that even the biggest box can't hold the
        # whole order in one go (on weight) -- forces a genuine multi-box
        # comparison across two different box types.
        qty = 1000
        line = make_line(l="5", w="5", h="5", weight="0.5", qty=qty)
        # Box A: small & cheap per-unit but needs MANY units.
        box_a = make_box(box_id=1, l="10", w="10", h="10", max_weight="5", cost="2.00")
        # Box B: bigger & pricier per-unit, but needs far fewer units -> cheaper overall.
        box_b = make_box(box_id=2, l="30", w="30", h="30", max_weight="50", cost="15.00")

        result = BoxRecommendationService([line], [box_a, box_b]).recommend()

        self.assertEqual(result.recommendation_type, "multi_box")

        eff = Decimal("0.85")

        def boxes_needed(box):
            weight_total = Decimal("0.5") * qty
            volume_total = Decimal("5") ** 3 * qty
            import math
            wb = math.ceil(weight_total / box.max_weight)
            vb = math.ceil(volume_total / (box.internal_volume * eff))
            return max(wb, vb, 1)

        cost_a = box_a.cost * boxes_needed(box_a)
        cost_b = box_b.cost * boxes_needed(box_b)
        expected_cost = min(cost_a, cost_b)
        # Sanity: this scenario is only meaningful if the two options
        # actually differ in cost.
        self.assertNotEqual(cost_a, cost_b)
        self.assertEqual(result.total_cost, expected_cost)

    # Edge case #16: even multi-box splitting fails because a single unit
    # is too large for every box -> definitive ITEM_TOO_LARGE failure.
    def test_multibox_not_viable_when_single_unit_too_large(self):
        line = make_line(l="500", w="500", h="500", weight="1", qty=2)
        box = make_box(l="20", w="20", h="20", max_weight="1000", cost="5.00")

        with self.assertRaises(NoSuitableBoxError) as ctx:
            BoxRecommendationService([line], [box]).recommend()

        self.assertEqual(ctx.exception.reason, ReasonCode.ITEM_TOO_LARGE)

    # Multiple distinct products where no single box type fits all lines
    # at once (each fits somewhere, but not the same box) -> clean failure,
    # not a silently wrong recommendation.
    def test_no_single_box_type_fits_all_distinct_lines(self):
        # Long, thin item: only fits a box with a long enough single dimension.
        line_a = make_line(product_id=1, l="5", w="5", h="35", weight="0.5", qty=1)
        # Bulky cube item: only fits a box whose SMALLEST dimension is large enough.
        line_b = make_line(product_id=2, l="25", w="25", h="25", weight="0.5", qty=1)

        narrow_but_long_box = make_box(box_id=1, l="10", w="10", h="40", max_weight="5", cost="5.00")
        cube_box = make_box(box_id=2, l="30", w="30", h="30", max_weight="5", cost="5.00")

        with self.assertRaises(NoSuitableBoxError) as ctx:
            BoxRecommendationService(
                [line_a, line_b], [narrow_but_long_box, cube_box]
            ).recommend()

        # Both lines individually fit in *some* box, so this must NOT be
        # misreported as ITEM_TOO_LARGE -- it's a combined-fit shortfall.
        self.assertEqual(ctx.exception.reason, ReasonCode.NO_BOXES_AVAILABLE)
