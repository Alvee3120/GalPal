"""Per-IP throttles for the two anonymous order endpoints (Module 18 will review throttling globally)."""
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
