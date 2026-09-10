from rest_framework import serializers

from products.models import Product


class ProductSerializer(serializers.ModelSerializer):
    volume_cm3 = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "length_cm",
            "width_cm",
            "height_cm",
            "weight_kg",
            "is_active",
            "volume_cm3",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
