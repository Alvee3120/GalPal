"""Reusable authentication classes."""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class OptionalJWTAuthentication(JWTAuthentication):
    """
    Like `JWTAuthentication`, but an invalid, expired or garbage token is treated as "no
    credentials" (the request proceeds as anonymous) instead of failing with 401.

    For endpoints that must serve both guests and logged-in users alike (e.g. the cart): a guest
    whose app still has a stale token lying around must not be locked out just for browsing. A
    *missing* token still authenticates as anonymous either way; only a present-but-bad one
    changes behaviour here.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError):
            return None


# --- OpenAPI schema ----------------------------------------------------------------------------

from drf_spectacular.extensions import OpenApiAuthenticationExtension  # noqa: E402


class OptionalJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Documents `OptionalJWTAuthentication` the same way drf-spectacular documents plain JWT auth."""

    target_class = OptionalJWTAuthentication
    name = "optionalJwtAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
