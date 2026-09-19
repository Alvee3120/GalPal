import logging

from django.conf import settings
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import error_body
from .serializers import HealthResponseSerializer

logger = logging.getLogger(__name__)


def check_database():
    """Return "ok" if PostgreSQL answers a trivial query, else "error"."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        logger.exception("Health check: database unreachable")
        return "error"
    return "ok"


class HealthCheckView(APIView):
    """Liveness/readiness probe for load balancers, Docker and uptime monitors."""

    authentication_classes = []
    permission_classes = [AllowAny]
    pagination_class = None

    @extend_schema(
        tags=["System"],
        summary="Health check",
        description="Returns 200 when the API and its database are reachable, 503 otherwise. "
        "Both responses use the same body so monitors can parse either.",
        auth=[],
        responses={200: HealthResponseSerializer, 503: HealthResponseSerializer},
    )
    def get(self, request):
        checks = {"database": check_database()}
        healthy = all(result == "ok" for result in checks.values())
        return Response(
            {
                "status": "ok" if healthy else "degraded",
                "service": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "time": timezone.now(),
                "checks": checks,
            },
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# --- Django-level error handlers (URLs that never reach DRF) -----------------


def _json_error(status_code, code, message):
    return JsonResponse(error_body(status_code, code, message), status=status_code)


def bad_request(request, exception=None):
    return _json_error(400, "bad_request", "Bad request.")


def permission_denied(request, exception=None):
    return _json_error(403, "permission_denied", "You do not have permission to perform this action.")


def not_found(request, exception=None):
    return _json_error(404, "not_found", "Not found.")


def server_error(request):
    return _json_error(500, "server_error", "A server error occurred.")
