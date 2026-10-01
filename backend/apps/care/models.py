"""
Customer care tools (Module 14, Admin only): care notes and tags on customers, the support inbox fed by the public
contact form, and abandoned checkouts captured at checkout.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class CustomerTag(TimeStampedModel):
    """A label Admin puts on customers (VIP, Risky, Wholesale…). Reusable across customers."""

    name = models.CharField(max_length=40, unique=True)
    customers = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="care_tags")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CustomerNote(TimeStampedModel):
    """An internal note about a customer, never shown to them."""

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="care_notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    text = models.TextField(max_length=2000)

    class Meta:
        ordering = ["-created_at"]


class MessageStatus(models.TextChoices):
    NEW = "new", "New"
    IN_PROGRESS = "in_progress", "In progress"
    RESOLVED = "resolved", "Resolved"


class ContactMessage(TimeStampedModel):
    """A message from the public contact form; Admin works it through New -> In progress -> Resolved."""

    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    subject = models.CharField(max_length=150, blank=True)
    message = models.TextField(max_length=5000)
    status = models.CharField(max_length=12, choices=MessageStatus.choices, default=MessageStatus.NEW, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.subject or self.message[:40]}"


class ContactMessageNote(TimeStampedModel):
    """Admin's reply/working note on a support message (internal; the reply itself goes out by phone/email)."""

    message = models.ForeignKey(ContactMessage, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    text = models.TextField(max_length=2000)

    class Meta:
        ordering = ["created_at"]


class CheckoutLeadStatus(models.TextChoices):
    OPEN = "open", "Not ordered"
    CONVERTED = "converted", "Ordered"
    DISMISSED = "dismissed", "Dismissed"


class CheckoutLead(TimeStampedModel):
    """
    An incomplete checkout: captured as soon as the shopper has typed a name and a valid phone at checkout. One open
    lead per phone (updated as they keep typing). Marked Converted automatically when that phone places an order.
    """

    phone = models.CharField(max_length=11, db_index=True)
    name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    district = models.CharField(max_length=60, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cart_snapshot = models.JSONField(default=list, blank=True, help_text="[{name, quantity, price}] at the last capture")
    cart_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=CheckoutLeadStatus.choices, default=CheckoutLeadStatus.OPEN, db_index=True)
    converted_order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-updated_at"]
