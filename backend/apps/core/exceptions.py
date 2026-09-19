"""
One JSON error format for the whole API.

    {
      "error": {
        "status": 400,
        "code": "validation_error",
        "message": "Validation failed.",
        "details": {"phone": ["This field is required."]}
      }
    }

* `code`    – stable machine-readable string the frontend can switch on
* `message` – human-readable summary
* `details` – field errors for validation failures (always a dict),
              `{"retry_after": seconds}` for throttling, extra data an exception
              carries (e.g. counts for a conflict), otherwise null
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.serializers import as_serializer_error
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

_STATUS_CODES = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "not_authenticated",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_406_NOT_ACCEPTABLE: "not_acceptable",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    status.HTTP_429_TOO_MANY_REQUESTS: "throttled",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "server_error",
}


def error_body(status_code, code, message, details=None):
    return {"error": {"status": status_code, "code": code, "message": message, "details": details}}


def api_exception_handler(exc, context):
    """DRF `EXCEPTION_HANDLER` that wraps every error in the envelope above."""
    if isinstance(exc, DjangoValidationError):
        # Raised from model.full_clean() / services; treat like a serializer error.
        exc = exceptions.ValidationError(detail=as_serializer_error(exc))

    response = drf_exception_handler(exc, context)

    if response is None:
        # Not something DRF knows how to render: log it and hide the internals.
        view = context.get("view")
        logger.exception("Unhandled exception in %s", view.__class__.__name__ if view else "view")
        return Response(
            error_body(500, "server_error", "A server error occurred."),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    if isinstance(exc, exceptions.ValidationError):
        data = response.data
        details = data if isinstance(data, dict) else {"non_field_errors": data}
        response.data = error_body(
            response.status_code, "validation_error", "Validation failed.", details
        )
        return response

    codes = exc.get_codes() if isinstance(exc, exceptions.APIException) else None
    if isinstance(codes, dict):
        # e.g. simplejwt's InvalidToken carries {"detail": "token_not_valid", ...}
        codes = codes.get("detail")
    code = codes if isinstance(codes, str) else _STATUS_CODES.get(response.status_code, "error")
    data = response.data
    message = data.get("detail", "An error occurred.") if isinstance(data, dict) else str(data)

    details = None
    if isinstance(exc, exceptions.Throttled) and exc.wait is not None:
        details = {"retry_after": int(exc.wait)}
    elif getattr(exc, "details", None) is not None:
        details = exc.details  # exceptions may attach structured details, e.g. {"children_count": 3}

    response.data = error_body(response.status_code, code, str(message), details)
    return response
