"""Per-IP throttles for the public newsletter and search endpoints."""
from apps.orders.throttles import _IPThrottle


class NewsletterThrottle(_IPThrottle):
    scope = "newsletter"
    setting_name = "NEWSLETTER_THROTTLE_RATE"


class SearchThrottle(_IPThrottle):
    scope = "search"
    setting_name = "SEARCH_THROTTLE_RATE"
