from rest_framework import serializers

from boxes.models import Box


class BoxSerializer(serializers.ModelSerializer):
    internal_volume_cm3 = serializers.ReadOnlyField()

    class Meta:
        model = Box
        fields = [
            "id",
            "name",
            "internal_length_cm",
            "internal_width_cm",
            "internal_height_cm",
            "max_weight_kg",
            "cost",
            "is_active",
            "internal_volume_cm3",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
