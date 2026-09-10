from decimal import Decimal

from django.test import SimpleTestCase, override_settings

from common.exceptions import InvalidOrderError, NoSuitableBoxError, ReasonCode
from recommendation.dto import BoxCandidate, Dimensions, OrderLine
from recommendation.services import BoxRecommendationService
from tests.test_services_happy_path import make_box, make_line


@override_settings(PACKING_EFFICIENCY_FACTOR=0.85, TIGHT_FIT_THRESHOLD=0.75)
class EdgeCaseTests(SimpleTestCase):
    # Edge case #1: no boxes in catalog at all.
    def test_no_boxes_available_raises(self):
        lines = [make_line()]
        with self.assertRaises(NoSuitableBoxError) as ctx:
            BoxRecommendationService(lines, []).recommend()
        self.assertEqual(ctx.exception.reason, ReasonCode.NO_BOXES_AVAILABLE)

    # Edge case #2: order has zero items.
    def test_empty_order_raises_invalid_order(self):
        with self.assertRaises(InvalidOrderError) as ctx:
            BoxRecommendationService([], [make_box()]).recommend()
        self.assertEqual(ctx.exception.reason, ReasonCode.EMPTY_ORDER)

    # Edge case #3: item exceeds every box in every rotation -> ITEM_TOO_LARGE,
    # distinguished from a general no-boxes-available failure.
    def test_item_too_large_for_any_box_is_flagged_distinctly(self):
        huge_line = make_line(l="1000", w="1000", h="1000", weight="1")
        box = make_box(l="20", w="20", h="20", max_weight="100")

        with self.assertRaises(NoSuitableBoxError) as ctx:
            BoxRecommendationService([huge_line], [box]).recommend()

        self.assertEqual(ctx.exception.reason, ReasonCode.ITEM_TOO_LARGE)

    # Edge case #4: total weight exceeds every box's max_weight even though
    # dimensions would fit, and multi-box splitting is also insufficient
    # only when even a single unit's weight can't be handled... here we
    # confirm weight alone correctly excludes an otherwise dimensionally
    # fine box from being a *single-box* candidate (falls through to multi-box).
    def test_weight_exceeded_falls_back_to_multi_box(self):
        line = make_line(l="2", w="2", h="2", weight="8", qty=3)  # total weight 24kg
        box = make_box(l="20", w="20", h="20", max_weight="10", cost="5.00")  # too heavy for 1 box

        result = BoxRecommendationService([line], [box]).recommend()

        self.assertEqual(result.recommendation_type, "multi_box")
        self.assertGreaterEqual(result.quantity, 3)  # ceil(24/10) = 3

    # Edge case #5: volume exceeds largest box even though each item fits
    # individually -> falls back to multi-box, not an outright failure.
    def test_volume_exceeded_falls_back_to_multi_box(self):
        line = make_line(l="10", w="10", h="10", weight="0.1", qty=50)  # big total volume
        box = make_box(l="20", w="20", h="20", max_weight="1000", cost="5.00")

        result = BoxRecommendationService([line], [box]).recommend()

        self.assertEqual(result.recommendation_type, "multi_box")

    # Edge case #7: extremely large quantity should not crash / overflow,
    # and should resolve via Decimal-safe multi-box math.
    def test_extremely_large_quantity_does_not_crash(self):
        line = make_line(l="1", w="1", h="1", weight="0.02", qty=100000)
        box = make_box(l="50", w="50", h="50", max_weight="1000", cost="5.00")

        result = BoxRecommendationService([line], [box]).recommend()

        self.assertEqual(result.recommendation_type, "multi_box")
        self.assertGreater(result.quantity, 1)

    # Edge case #8: two boxes tie on cost -> deterministic tie-break,
    # never dependent on input ordering.
    def test_deterministic_tie_break_regardless_of_input_order(self):
        line = make_line()
        box_a = make_box(box_id=10, l="25", w="25", h="25", cost="12.00")
        box_b = make_box(box_id=4, l="20", w="20", h="20", cost="12.00")

        result_1 = BoxRecommendationService([line], [box_a, box_b]).recommend()
        result_2 = BoxRecommendationService([line], [box_b, box_a]).recommend()

        self.assertEqual(result_1.box.box_id, result_2.box.box_id)
        self.assertEqual(result_1.box.box_id, 4)  # smaller volume wins the tie

    # Edge case #12: Decimal precision -- repeated fractional additions
    # must not drift due to float rounding.
    def test_decimal_precision_no_drift(self):
        line = make_line(l="1", w="1", h="1", weight="0.1", qty=3)  # 0.1 * 3 in float = 0.30000000000000004
        box = make_box(l="20", w="20", h="20", max_weight="10")

        result = BoxRecommendationService([line], [box]).recommend()

        self.assertEqual(result.total_weight, Decimal("0.3"))

    # Case: quantity must be positive (defensive; normally blocked by
    # serializer/model layer before reaching the service).
    def test_zero_quantity_line_raises_invalid_order(self):
        bad_line = make_line(qty=0)
        with self.assertRaises(InvalidOrderError):
            BoxRecommendationService([bad_line], [make_box()]).recommend()
