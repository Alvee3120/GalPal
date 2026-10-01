"""Per-IP throttles for the anonymous order endpoints: checkout, order tracking, and account creation at checkout."""
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class _IPThrottle(SimpleRateThrottle):
    setting_name = ""

    def get_rate(self):  # read at request time so it can be tuned (and overridden in tests) via settings
        return getattr(settings, self.setting_name)

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class CheckoutThrottle(_IPThrottle):
    scope = "checkout"
    setting_name = "CHECKOUT_THROTTLE_RATE"


class TrackOrderThrottle(_IPThrottle):
    scope = "order-track"
    setting_name = "ORDER_TRACK_THROTTLE_RATE"


class GuestAccountThrottle(_IPThrottle):
    """
    Checkout with `save_details=true` creates an account and emails its password, so it's limited much more tightly
    than checkout itself (spam accounts, email bombing). Only those requests count.
    """

    scope = "guest-account"
    setting_name = "GUEST_ACCOUNT_THROTTLE_RATE"

    def allow_request(self, request, view):
        try:
            wants_account = str(request.data.get("save_details", "")).lower() in ("true", "1", "on", "yes")
        except Exception:  # noqa: BLE001
            wants_account = False
        if not wants_account or (request.user and request.user.is_authenticated):
            return True
        return super().allow_request(request, view)
