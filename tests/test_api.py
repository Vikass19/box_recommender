from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import BoxFactory, ProductFactory


class RecommendBoxAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/recommend-box/"

    def test_happy_path_single_box(self):
        product = ProductFactory(length_cm="10", width_cm="10", height_cm="10", weight_kg="1")
        BoxFactory(internal_length_cm="30", internal_width_cm="30", internal_height_cm="30",
                   max_weight_kg="10", cost="15.00")

        response = self.client.post(
            self.url, {"items": [{"product_id": product.id, "quantity": 1}]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["recommendation_type"], "single_box")

    def test_multi_box_response_shape(self):
        product = ProductFactory(length_cm="10", width_cm="10", height_cm="10", weight_kg="5")
        BoxFactory(internal_length_cm="20", internal_width_cm="20", internal_height_cm="20",
                   max_weight_kg="10", cost="8.00")

        response = self.client.post(
            self.url, {"items": [{"product_id": product.id, "quantity": 10}]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["recommendation_type"], "multi_box")
        self.assertIn("quantity", response.data)
        self.assertIn("total_cost", response.data)

    # Edge case #2: empty items list -> 400
    def test_empty_items_returns_400(self):
        response = self.client.post(self.url, {"items": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Edge case #10: missing/non-numeric fields -> 400 via serializer
    def test_missing_quantity_field_returns_400(self):
        product = ProductFactory()
        response = self.client.post(
            self.url, {"items": [{"product_id": product.id}]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_numeric_product_id_returns_400(self):
        response = self.client.post(
            self.url, {"items": [{"product_id": "abc", "quantity": 1}]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Edge case #18: unknown product_id -> 400 with clear reason
    def test_unknown_product_id_returns_400(self):
        response = self.client.post(
            self.url, {"items": [{"product_id": 999999, "quantity": 1}]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "INVALID_PRODUCT")

    # Edge case #11: inactive product referenced -> flagged, not silently computed
    def test_inactive_product_returns_400(self):
        product = ProductFactory(is_active=False)
        response = self.client.post(
            self.url, {"items": [{"product_id": product.id, "quantity": 1}]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "INVALID_PRODUCT")

    # Edge case #19: duplicate product_id lines are aggregated, not doubled up as errors
    def test_duplicate_product_id_lines_are_aggregated(self):
        product = ProductFactory(length_cm="5", width_cm="5", height_cm="5", weight_kg="0.5")
        BoxFactory(internal_length_cm="30", internal_width_cm="30", internal_height_cm="30",
                   max_weight_kg="10", cost="10.00")

        response = self.client.post(
            self.url,
            {"items": [
                {"product_id": product.id, "quantity": 2},
                {"product_id": product.id, "quantity": 3},
            ]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # total_weight should reflect quantity 5, not two separate lines of 2 and 3
        self.assertEqual(response.data["total_weight"], "2.500")

    # Edge case #1: no boxes in catalog -> 422 with reason
    def test_no_boxes_in_catalog_returns_422(self):
        product = ProductFactory()
        response = self.client.post(
            self.url, {"items": [{"product_id": product.id, "quantity": 1}]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["error"], "NO_BOXES_AVAILABLE")

    # Edge case #3: item too large for any box -> 422 with ITEM_TOO_LARGE
    def test_item_too_large_returns_422(self):
        product = ProductFactory(length_cm="1000", width_cm="1000", height_cm="1000", weight_kg="1")
        BoxFactory(internal_length_cm="20", internal_width_cm="20", internal_height_cm="20",
                   max_weight_kg="10", cost="10.00")

        response = self.client.post(
            self.url, {"items": [{"product_id": product.id, "quantity": 1}]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.data["error"], "ITEM_TOO_LARGE")

    # Model validation is exercised through the ModelViewSet create endpoint too.
    def test_creating_product_with_invalid_dimension_via_api_returns_400(self):
        response = self.client.post(
            "/api/products/",
            {
                "name": "Bad Product",
                "sku": "BAD-001",
                "length_cm": "0",
                "width_cm": "10",
                "height_cm": "10",
                "weight_kg": "1",
            },
            format="json",
        )
        # DRF ModelSerializer relies on field-level validators; a
        # DecimalField with a positive-only validator should reject this.
        self.assertIn(response.status_code, (status.HTTP_400_BAD_REQUEST,))
