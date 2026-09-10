"""
Global DRF exception handler.

Maps our domain exceptions (common/exceptions.py) to consistent HTTP
responses, so every endpoint returns the same error shape instead of
each view hand-rolling try/except blocks. Falls through to DRF's
default handler for anything else (e.g. its own ValidationError),
so standard serializer errors still work normally.
"""

from rest_framework.views import exception_handler as drf_default_exception_handler
from rest_framework.response import Response
from rest_framework import status

from common.exceptions import (
    BoxRecommendationError,
    InvalidOrderError,
    InvalidDimensionError,
    NoSuitableBoxError,
)

_STATUS_MAP = {
    InvalidOrderError: status.HTTP_400_BAD_REQUEST,
    InvalidDimensionError: status.HTTP_400_BAD_REQUEST,
    NoSuitableBoxError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def custom_exception_handler(exc, context):
    if isinstance(exc, BoxRecommendationError):
        http_status = _STATUS_MAP.get(type(exc), status.HTTP_400_BAD_REQUEST)
        payload = {
            "error": exc.reason,
            "message": exc.message,
        }
        if exc.detail:
            payload["detail"] = exc.detail
        return Response(payload, status=http_status)

    # Fall back to DRF's default handling (e.g. serializer ValidationError,
    # NotFound, PermissionDenied, etc.)
    return drf_default_exception_handler(exc, context)
