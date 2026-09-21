from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.exceptions import APIException


def field_error(field, message, code):
    """A `ValidationError` on one field whose `code` survives (dict-form errors drop a top-level code)."""
    return ValidationError({field: ValidationError(message, code=code)})


class ShippingNotConfigured(APIException):
    """503: there is no active default zone, so an unmatched address has nowhere to fall back to."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Delivery charges are not configured yet."
    default_code = "shipping_not_configured"
