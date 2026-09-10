"""
Custom exception hierarchy for the box recommendation domain.

Each exception carries a machine-readable `reason` code so API
consumers (and the warehouse team's tooling) can branch on the cause
without parsing free-text messages. These are plain Python exceptions
(no DRF/Django coupling) so the `recommendation` service layer stays
framework-agnostic and independently testable. The DRF-specific mapping
to HTTP responses lives in common/exception_handlers.py.
"""


class ReasonCode:
    """Namespace of machine-readable reason codes used across exceptions."""

    ITEM_TOO_LARGE = "ITEM_TOO_LARGE"
    WEIGHT_EXCEEDED = "WEIGHT_EXCEEDED"
    VOLUME_EXCEEDED = "VOLUME_EXCEEDED"
    NO_BOXES_AVAILABLE = "NO_BOXES_AVAILABLE"
    EMPTY_ORDER = "EMPTY_ORDER"
    INVALID_PRODUCT = "INVALID_PRODUCT"
    INVALID_DIMENSION = "INVALID_DIMENSION"


class BoxRecommendationError(Exception):
    """Base class for all domain errors raised by the recommendation service."""

    default_reason = "UNKNOWN_ERROR"

    def __init__(self, message, reason=None, detail=None):
        self.message = message
        self.reason = reason or self.default_reason
        # Optional structured extra context (e.g. attempted candidates),
        # surfaced to the API response payload for actionability.
        self.detail = detail or {}
        super().__init__(message)


class InvalidOrderError(BoxRecommendationError):
    """Raised when the order itself is malformed (e.g. no items, bad product ref)."""

    default_reason = ReasonCode.EMPTY_ORDER


class InvalidDimensionError(BoxRecommendationError):
    """Raised when a dimension/weight/cost value is invalid (defense in depth;
    normally caught earlier by model/serializer validation)."""

    default_reason = ReasonCode.INVALID_DIMENSION


class NoSuitableBoxError(BoxRecommendationError):
    """Raised when no single box or multi-box split can satisfy the order."""

    default_reason = ReasonCode.NO_BOXES_AVAILABLE
