"""Coupon apply throttle (Module 18): stops guessing coupon codes by brute force. Per client IP."""
from apps.accounts.throttles import IPRateThrottle


class CouponApplyThrottle(IPRateThrottle):
    scope = "coupon-apply"
    setting_name = "COUPON_APPLY_THROTTLE_RATE"

    def allow_request(self, request, view):
        if request.method != "POST":  # removing a coupon is never limited
            return True
        return super().allow_request(request, view)
