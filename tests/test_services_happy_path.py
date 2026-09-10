from decimal import Decimal

from django.test import SimpleTestCase, override_settings

from recommendation.dto import BoxCandidate, Dimensions, OrderLine
from recommendation.services import BoxRecommendationService


def make_line(product_id=1, name="Widget", l="10", w="10", h="10", weight="1.0", qty=1):
    return OrderLine(
        product_id=product_id,
        product_name=name,
        dimensions=Dimensions(Decimal(l), Decimal(w), Decimal(h)),
        unit_weight=Decimal(weight),
        quantity=qty,
    )


def make_box(box_id=1, name="Small", l="20", w="20", h="20", max_weight="5.0", cost="10.00"):
    return BoxCandidate(
        box_id=box_id,
        name=name,
        dimensions=Dimensions(Decimal(l), Decimal(w), Decimal(h)),
        max_weight=Decimal(max_weight),
        cost=Decimal(cost),
    )


@override_settings(PACKING_EFFICIENCY_FACTOR=0.85, TIGHT_FIT_THRESHOLD=0.75)
class SingleBoxHappyPathTests(SimpleTestCase):
    def test_recommends_cheapest_valid_box(self):
        lines = [make_line()]
        small = make_box(box_id=1, cost="10.00")
        medium = make_box(box_id=2, name="Medium", l="40", w="40", h="40", max_weight="20", cost="20.00")

        result = BoxRecommendationService(lines, [medium, small]).recommend()

        self.assertEqual(result.recommendation_type, "single_box")
        self.assertEqual(result.box.box_id, 1)  # cheapest that fits

    def test_confidence_comfortable_when_plenty_of_headroom(self):
        lines = [make_line(l="2", w="2", h="2", weight="0.1")]
        box = make_box(l="30", w="30", h="30", max_weight="10")

        result = BoxRecommendationService(lines, [box]).recommend()

        self.assertEqual(result.confidence, "comfortable")

    def test_confidence_tight_when_near_capacity(self):
        # Box usable volume = 20*20*20*0.85 = 6800; item volume ~ 6700 -> ratio > 0.75
        lines = [make_line(l="18.9", w="18.9", h="18.9", weight="1")]
        box = make_box(l="20", w="20", h="20", max_weight="10")

        result = BoxRecommendationService(lines, [box]).recommend()

        self.assertEqual(result.recommendation_type, "single_box")
        self.assertEqual(result.confidence, "tight")

    def test_tie_break_by_smallest_volume_then_id(self):
        lines = [make_line()]
        box_a = make_box(box_id=5, l="25", w="25", h="25", cost="15.00")
        box_b = make_box(box_id=3, l="20", w="20", h="20", cost="15.00")  # smaller volume, same cost

        result = BoxRecommendationService(lines, [box_a, box_b]).recommend()

        self.assertEqual(result.box.box_id, 3)

    def test_rotation_allows_fit_when_axis_mismatched(self):
        # Item is long and thin (50x5x5); box is 10x10x60 -- only fits if rotated.
        lines = [make_line(l="50", w="5", h="5", weight="1")]
        box = make_box(l="10", w="10", h="60", max_weight="5")

        result = BoxRecommendationService(lines, [box]).recommend()

        self.assertEqual(result.recommendation_type, "single_box")

    def test_multiple_different_products_in_one_order(self):
        line1 = make_line(product_id=1, l="5", w="5", h="5", weight="0.5", qty=2)
        line2 = make_line(product_id=2, name="Gadget", l="3", w="3", h="3", weight="0.2", qty=4)
        box = make_box(l="20", w="20", h="20", max_weight="5")

        result = BoxRecommendationService([line1, line2], [box]).recommend()

        self.assertEqual(result.recommendation_type, "single_box")
        self.assertEqual(result.total_weight, Decimal("0.5") * 2 + Decimal("0.2") * 4)
