"""
Request-side serializers for the recommend-box endpoint. Response
shaping (converting a Single/MultiBoxRecommendation into the documented
JSON contract) is handled directly in views.py since it operates on
plain dataclasses, not model instances.
"""

from rest_framework import serializers


class RecommendationItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class RecommendationRequestSerializer(serializers.Serializer):
    items = RecommendationItemInputSerializer(many=True, allow_empty=False)
