"""Per-IP throttles for the two public care endpoints (contact form, checkout capture)."""
from apps.orders.throttles import _IPThrottle


class ContactThrottle(_IPThrottle):
    scope = "contact"
    setting_name = "CONTACT_THROTTLE_RATE"


class CheckoutLeadThrottle(_IPThrottle):
    scope = "checkout-lead"
    setting_name = "CHECKOUT_LEAD_THROTTLE_RATE"
