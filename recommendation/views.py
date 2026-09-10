"""
Thin API view: parses/validates the request, builds DTOs from the DB,
delegates entirely to BoxRecommendationService, and shapes the result
into the documented JSON response. No box-fitting logic lives here.
"""

from collections import OrderedDict
from decimal import Decimal

from rest_framework.response import Response
from rest_framework.views import APIView

from boxes.models import Box
from common.exceptions import InvalidOrderError, ReasonCode
from products.models import Product
from recommendation.dto import BoxCandidate, Dimensions, OrderLine
from recommendation.serializers import RecommendationRequestSerializer
from recommendation.services import BoxRecommendationService


def _load_boxes():
    return [
        BoxCandidate(
            box_id=box.id,
            name=box.name,
            dimensions=Dimensions(box.internal_length_cm, box.internal_width_cm, box.internal_height_cm),
            max_weight=box.max_weight_kg,
            cost=box.cost,
        )
        for box in Box.objects.filter(is_active=True)
    ]


def _build_order_lines(items):
    """Resolve raw (product_id, quantity) request items into OrderLine
    DTOs. Aggregates duplicate product_ids (edge case #19: duplicate
    product_id in same request is summed, not treated as two lines).
    Raises InvalidOrderError for unknown or inactive products (edge
    case #11 & #18) rather than silently skipping them.
    """
    quantities = OrderedDict()
    for item in items:
        pid = item["product_id"]
        quantities[pid] = quantities.get(pid, 0) + item["quantity"]

    product_ids = list(quantities.keys())
    products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}

    missing = [pid for pid in product_ids if pid not in products]
    if missing:
        raise InvalidOrderError(
            f"Unknown product_id(s): {missing}",
            reason=ReasonCode.INVALID_PRODUCT,
            detail={"missing_product_ids": missing},
        )

    inactive = [pid for pid in product_ids if not products[pid].is_active]
    if inactive:
        raise InvalidOrderError(
            f"Product_id(s) {inactive} are inactive/discontinued and cannot be "
            "recommended for; the order must be corrected before boxing.",
            reason=ReasonCode.INVALID_PRODUCT,
            detail={"inactive_product_ids": inactive},
        )

    lines = []
    for pid, qty in quantities.items():
        product = products[pid]
        lines.append(
            OrderLine(
                product_id=product.id,
                product_name=product.name,
                dimensions=Dimensions(product.length_cm, product.width_cm, product.height_cm),
                unit_weight=product.weight_kg,
                quantity=qty,
            )
        )
    return lines


def _serialize_box(box: BoxCandidate):
    return {"id": box.box_id, "name": box.name, "cost": str(box.cost)}


def _decimal_str(value: Decimal) -> str:
    return str(value)


class RecommendBoxView(APIView):
    """POST /api/recommend-box/

    Request:  {"items": [{"product_id": 1, "quantity": 3}, ...]}
    Response: see recommendation/README section of the project docs for
    the full single_box / multi_box / error shapes.
    """

    def post(self, request):
        serializer = RecommendationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_lines = _build_order_lines(serializer.validated_data["items"])
        boxes = _load_boxes()

        service = BoxRecommendationService(order_lines=order_lines, boxes=boxes)
        result = service.recommend()  # raises on failure; handled by global exception handler

        if result.recommendation_type == "single_box":
            payload = {
                "recommendation_type": "single_box",
                "box": _serialize_box(result.box),
                "confidence": result.confidence,
                "total_weight": _decimal_str(result.total_weight),
                "total_volume": _decimal_str(result.total_volume),
            }
        else:
            payload = {
                "recommendation_type": "multi_box",
                "box": _serialize_box(result.box),
                "quantity": result.quantity,
                "total_cost": _decimal_str(result.total_cost),
                "reason": result.reason,
            }

        return Response(payload)
