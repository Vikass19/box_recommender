from django.core.validators import MinValueValidator
from django.db import models

from common.models import TimeStampedModel
from products.models import Product


class Order(TimeStampedModel):
    """A customer order. Persisted so recommendations can be re-run /
    audited later, even though the recommend-box API also accepts raw
    (product_id, quantity) pairs directly without requiring a saved Order.
    """

    reference = models.CharField(max_length=64, unique=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference or f"Order #{self.pk}"


class OrderItem(TimeStampedModel):
    """A single line item within an order: a product and how many units."""

    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name="order_items", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        # Edge case #19: duplicate product_id in the same order is
        # aggregated at the service layer, but we still prevent two raw
        # DB rows for the same (order, product) to keep persisted data clean.
        unique_together = ("order", "product")

    def __str__(self):
        return f"{self.product} x{self.quantity}"
