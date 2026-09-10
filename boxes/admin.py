from django.contrib import admin

from boxes.models import Box


@admin.register(Box)
class BoxAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "internal_length_cm",
        "internal_width_cm",
        "internal_height_cm",
        "max_weight_kg",
        "cost",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
