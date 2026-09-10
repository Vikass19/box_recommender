from django.contrib import admin

from products.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "length_cm", "width_cm", "height_cm", "weight_kg", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "sku")
