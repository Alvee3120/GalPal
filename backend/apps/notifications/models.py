"""
Notifications (Module 16): editable message templates and a log of every email/SMS the shop sends.

A secret in a message (a password-reset code, a generated password) is sent but never stored: the log keeps the body
with each secret replaced by a mask, so the log is safe for staff to read.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Event(models.TextChoices):
    ORDER_PLACED = "order_placed", "Order placed"
    ORDER_STATUS = "order_status_changed", "Order status changed"
    PASSWORD_RESET = "password_reset_otp", "Password reset code"
    NEW_ACCOUNT = "new_account", "New account details"
    LOW_STOCK = "low_stock", "Low stock alert (to admins)"
    REVIEW_REPLY = "review_reply", "Reply to a review"
    BACK_IN_STOCK = "back_in_stock", "Back in stock (Notify Me)"


class Channel(models.TextChoices):
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"


class NotificationTemplate(TimeStampedModel):
    """An Admin's override of the built-in text for one event + channel (services.DEFAULT_TEMPLATES)."""

    event = models.CharField(max_length=30, choices=Event.choices)
    channel = models.CharField(max_length=5, choices=Channel.choices)
    subject = models.CharField(max_length=200, blank=True, help_text="Email only.")
    body = models.TextField(max_length=5000)
    is_active = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["event", "channel"]
        constraints = [models.UniqueConstraint(fields=["event", "channel"], name="notification_template_unique_event_channel")]

    def __str__(self):
        return f"{self.get_event_display()} ({self.channel})"


class LogStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RETRYING = "retrying", "Retrying"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class NotificationLog(TimeStampedModel):
    event = models.CharField(max_length=30, choices=Event.choices, db_index=True)
    channel = models.CharField(max_length=5, choices=Channel.choices, db_index=True)
    recipient = models.CharField(max_length=254, db_index=True)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(help_text="As sent, except secrets (codes, passwords), which are masked.")
    has_secret = models.BooleanField(default=False, help_text="The real message held a secret, so it can't be re-sent from the log.")
    status = models.CharField(max_length=10, choices=LogStatus.choices, default=LogStatus.QUEUED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="notifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="notifications")

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.event} → {self.recipient} ({self.status})"
