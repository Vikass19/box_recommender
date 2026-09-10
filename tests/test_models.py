from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from tests.factories import BoxFactory, ProductFactory


class ProductValidationTests(TestCase):
    def test_valid_product_saves_cleanly(self):
        product = ProductFactory()
        product.full_clean()  # should not raise

    def test_zero_dimension_rejected(self):
        product = ProductFactory.build(length_cm=Decimal("0"))
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_negative_weight_rejected(self):
        product = ProductFactory.build(weight_kg=Decimal("-1.5"))
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_volume_property_computed_correctly(self):
        product = ProductFactory(
            length_cm=Decimal("2.00"), width_cm=Decimal("3.00"), height_cm=Decimal("4.00")
        )
        self.assertEqual(product.volume_cm3, Decimal("24.00").quantize(product.volume_cm3))


class BoxValidationTests(TestCase):
    def test_valid_box_saves_cleanly(self):
        box = BoxFactory()
        box.full_clean()

    def test_zero_max_weight_rejected(self):
        box = BoxFactory.build(max_weight_kg=Decimal("0"))
        with self.assertRaises(ValidationError):
            box.full_clean()

    def test_negative_cost_rejected(self):
        box = BoxFactory.build(cost=Decimal("-5.00"))
        with self.assertRaises(ValidationError):
            box.full_clean()

    def test_sorted_internal_dims(self):
        box = BoxFactory(
            internal_length_cm=Decimal("10"),
            internal_width_cm=Decimal("30"),
            internal_height_cm=Decimal("20"),
        )
        self.assertEqual(box.sorted_internal_dims(), (Decimal("10"), Decimal("20"), Decimal("30")))
