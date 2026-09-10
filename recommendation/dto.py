"""
Framework-agnostic data transfer objects for the recommendation service.

These are plain dataclasses (no Django ORM dependency) so the service
and strategies layers can be unit tested without a database, and so the
same logic could later be reused outside of Django/DRF if needed.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Dimensions:
    """A length/width/height value object.

    Centralising rotation/sorting logic here means every place that
    needs to compare two boxes' worth of dimensions (products vs boxes)
    uses the exact same method — avoids re-deriving "does A fit in B"
    logic in multiple files (DRY).
    """

    length: Decimal
    width: Decimal
    height: Decimal

    def sorted_dims(self) -> Tuple[Decimal, Decimal, Decimal]:
        """Dimensions sorted ascending (smallest, middle, largest)."""
        return tuple(sorted([self.length, self.width, self.height]))

    def fits_in(self, other: "Dimensions") -> bool:
        """True if this item fits inside `other` in SOME axis-aligned
        rotation (of the up to 6 possible orientations).

        Sorting both dimension triples ascending and comparing
        element-wise is mathematically equivalent to checking all 6
        rotations for a single item fitting in a single box — if the
        sorted item dims are <= the sorted box dims in every position,
        some rotation of the item fits; otherwise none do.
        """
        mine = self.sorted_dims()
        theirs = other.sorted_dims()
        return all(m <= t for m, t in zip(mine, theirs))

    @property
    def volume(self) -> Decimal:
        return self.length * self.width * self.height


@dataclass(frozen=True)
class OrderLine:
    """A single resolved order line: a product's dimensions/weight and
    the quantity ordered. Decoupled from the Product model so the
    service can be fed either real ORM objects or test fixtures.
    """

    product_id: int
    product_name: str
    dimensions: Dimensions
    unit_weight: Decimal
    quantity: int

    @property
    def line_weight(self) -> Decimal:
        return self.unit_weight * self.quantity

    @property
    def line_volume(self) -> Decimal:
        return self.dimensions.volume * self.quantity


@dataclass(frozen=True)
class BoxCandidate:
    """A box's data as seen by the recommendation engine."""

    box_id: int
    name: str
    dimensions: Dimensions
    max_weight: Decimal
    cost: Decimal

    @property
    def internal_volume(self) -> Decimal:
        return self.dimensions.volume


@dataclass
class SingleBoxRecommendation:
    recommendation_type: str = field(default="single_box", init=False)
    box: BoxCandidate = None
    confidence: str = "comfortable"  # "comfortable" | "tight"
    total_weight: Decimal = Decimal("0")
    total_volume: Decimal = Decimal("0")


@dataclass
class MultiBoxRecommendation:
    recommendation_type: str = field(default="multi_box", init=False)
    box: BoxCandidate = None
    quantity: int = 0
    total_cost: Decimal = Decimal("0")
    reason: str = ""
