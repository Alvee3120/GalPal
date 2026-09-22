from django.conf import settings
from django.db import models

from apps.orders.models import Order


class TrackingEventName(models.TextChoices):
    PAGE_VIEW = "PageView", "PageView"
    VIEW_CONTENT = "ViewContent", "ViewContent"
    ADD_TO_CART = "AddToCart", "AddToCart"
    INITIATE_CHECKOUT = "InitiateCheckout", "InitiateCheckout"
    PURCHASE = "Purchase", "Purchase"


class TrackingDestination(models.TextChoices):
    META_CAPI = "meta_capi", "Meta Conversions API"
    GA4 = "ga4", "GA4 Measurement Protocol"


class TrackingEventLog(models.Model):
    """
    One attempt to send one event to one destination — a real record for debugging, not a cache.
    A retried send (Celery) writes another row (`attempt` going up), it never overwrites the last
    one, so the full history of what was tried survives even when it eventually succeeds.

    `request_payload` is exactly what was sent: PII (email/phone/name) is already SHA-256 hashed by
    `services.build_user_data` before it ever reaches this row, per Meta's rules — nothing here is
    reversible to a real email or phone number. The access token itself is never in this payload
    (it travels as a query parameter, not the request body).
    """

    event_name = models.CharField(max_length=20, choices=TrackingEventName.choices, db_index=True)
    destination = models.CharField(max_length=10, choices=TrackingDestination.choices, db_index=True)
    event_id = models.CharField(max_length=100, blank=True, db_index=True, help_text="The frontend/order-derived id used to dedupe the browser pixel against this server-side send.")

    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="tracking_events")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_manual_order = models.BooleanField(default=False, help_text="Copied from the order at send time, so this stays meaningful even if the order changes later.")

    request_payload = models.JSONField(default=dict, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=False, db_index=True)
    error_message = models.CharField(max_length=500, blank=True)
    attempt = models.PositiveSmallIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["event_name", "destination", "-created_at"])]

    def __str__(self):
        return f"{self.event_name} -> {self.destination}: {'ok' if self.success else 'failed'}"
