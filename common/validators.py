"""
Reusable field validators shared by Product and Box models.

DRY rationale: both Product (length/width/height/weight) and Box
(internal_length/internal_width/internal_height/max_weight/cost) need
"must be a positive, non-zero number" validation. Instead of repeating
MinValueValidator(Decimal("0.01")) everywhere with slightly different
messages, both models import from here.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError


def validate_positive_nonzero(value):
    """Raise ValidationError if value is not strictly greater than zero.

    Applies to dimensions, weight, and cost fields. Zero or negative
    values are physically meaningless (a box with 0 height, a product
    with negative weight) and must never reach the recommendation
    service — they are rejected here, at the model layer.
    """
    if value is None:
        raise ValidationError("This field is required.")
    if value <= Decimal("0"):
        raise ValidationError(
            "%(value)s is not a valid value: must be greater than zero.",
            params={"value": value},
        )
