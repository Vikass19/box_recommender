from decimal import Decimal

from django.db import models

from common.models import TimeStampedModel
from common.validators import validate_positive_nonzero


class Product(TimeStampedModel):
    """A sellable product with physical dimensions and weight.

    All dimension/weight fields use Decimal (never float) to avoid
    floating point precision drift when summing across large order
    quantities (see edge case: accumulated rounding error).
    """

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, unique=True)

    length_cm = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[validate_positive_nonzero]
    )
    width_cm = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[validate_positive_nonzero]
    )
    height_cm = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[validate_positive_nonzero]
    )
    weight_kg = models.DecimalField(
        max_digits=8, decimal_places=3, validators=[validate_positive_nonzero]
    )

    # Soft-delete / catalog flag. Referenced by an existing order but no
    # longer sellable — recommendation service must not silently ignore
    # this; see edge case #11.
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def volume_cm3(self) -> Decimal:
        return Decimal(self.length_cm) * Decimal(self.width_cm) * Decimal(self.height_cm)
