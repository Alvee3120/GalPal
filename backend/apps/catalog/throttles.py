"""Per-IP throttle for the anonymous "Notify Me" endpoint (same pattern as apps.orders.throttles)."""
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class StockNotificationThrottle(SimpleRateThrottle):
    scope = "stock-notification"

    def get_rate(self):  # read at request time so it can be tuned (and overridden in tests) via settings
        return settings.STOCK_NOTIFICATION_THROTTLE_RATE

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
