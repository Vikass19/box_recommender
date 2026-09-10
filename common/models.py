from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model providing self-updating created_at / updated_at fields.

    DRY rationale: Product, Box, Order, and OrderItem all need audit
    timestamps. Without this, each model would repeat the same two
    field definitions. Any future model in this project should inherit
    from this instead of redefining timestamps.
    """

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
