from decimal import Decimal

from django.db import models

from common.models import TimeStampedModel
from common.validators import validate_positive_nonzero


class Box(TimeStampedModel):
    """A shipping box available in the warehouse catalog.

    Dimensions are INTERNAL usable dimensions (not outer box size) —
    this is what actually constrains what can be packed inside.
    """

    name = models.CharField(max_length=100)
    internal_length_cm = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[validate_positive_nonzero]
    )
    internal_width_cm = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[validate_positive_nonzero]
    )
    internal_height_cm = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[validate_positive_nonzero]
    )
    max_weight_kg = models.DecimalField(
        max_digits=8, decimal_places=3, validators=[validate_positive_nonzero]
    )
    cost = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[validate_positive_nonzero]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["cost"]

    def __str__(self):
        return self.name

    @property
    def internal_volume_cm3(self) -> Decimal:
        return (
            Decimal(self.internal_length_cm)
            * Decimal(self.internal_width_cm)
            * Decimal(self.internal_height_cm)
        )

    def sorted_internal_dims(self):
        """Internal dimensions sorted ascending — used for rotation-agnostic
        fit comparisons. Returns a tuple (smallest, middle, largest)."""
        dims = [
            Decimal(self.internal_length_cm),
            Decimal(self.internal_width_cm),
            Decimal(self.internal_height_cm),
        ]
        return tuple(sorted(dims))
