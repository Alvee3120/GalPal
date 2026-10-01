"""
Throttles for the public auth endpoints (Module 18): brute-force and SMS/email-bombing protection.

Each endpoint gets two limits: per client IP (kept generous — Bangladeshi mobile networks put many customers behind
one shared IP) and per account identifier (the real defence: one phone/email can't be hammered from many IPs).
Identifiers are hashed in the cache key, so no phone number or email sits in Redis. Rates come from settings and are
read at request time.
"""

import hashlib

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

from apps.core.validators import normalize_bd_phone


class IPRateThrottle(SimpleRateThrottle):
    setting_name = ""

    def get_rate(self):
        return getattr(settings, self.setting_name)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def identifier_key(value):
    value = str(value or "").strip().lower()
    if not value:
        return None
    if "@" not in value:
        try:
            value = normalize_bd_phone(value)
        except Exception:  # noqa: BLE001 - not a valid phone: throttle the raw text instead
            pass
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


class IdentifierRateThrottle(IPRateThrottle):
    """Keyed by the `identifier` in the request body; no identifier → not limited here (the IP throttle still is)."""

    field = "identifier"

    def get_cache_key(self, request, view):
        try:
            ident = identifier_key(request.data.get(self.field))
        except Exception:  # noqa: BLE001 - unparseable body: the view will reject it anyway
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident} if ident else None


class LoginThrottle(IPRateThrottle):
    scope = "login"
    setting_name = "LOGIN_THROTTLE_RATE"


class LoginIdentifierThrottle(IdentifierRateThrottle):
    scope = "login-identifier"
    setting_name = "LOGIN_IDENTIFIER_THROTTLE_RATE"


class RegisterThrottle(IPRateThrottle):
    scope = "register"
    setting_name = "REGISTER_THROTTLE_RATE"


class PasswordResetRequestThrottle(IPRateThrottle):
    scope = "otp-request"
    setting_name = "OTP_REQUEST_THROTTLE_RATE"


class PasswordResetRequestIdentifierThrottle(IdentifierRateThrottle):
    scope = "otp-request-identifier"
    setting_name = "OTP_REQUEST_IDENTIFIER_THROTTLE_RATE"


class PasswordResetVerifyThrottle(IPRateThrottle):
    scope = "otp-verify"
    setting_name = "OTP_VERIFY_THROTTLE_RATE"


class PasswordResetVerifyIdentifierThrottle(IdentifierRateThrottle):
    scope = "otp-verify-identifier"
    setting_name = "OTP_VERIFY_IDENTIFIER_THROTTLE_RATE"
