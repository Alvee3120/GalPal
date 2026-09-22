from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel
from apps.orders.models import Order, PaymentMethod, PaymentStatus

_min_zero = MinValueValidator(Decimal("0"))


class RefundStatus(models.TextChoices):
    """
    Currently every `Refund` ends up COMPLETED: a row is the admin declaring money has already been
    returned (cash handed back, or processed through the gateway's own dashboard) — there is no
    gateway-initiated refund API in this module (the spec's gateway interface is initiate/callback/
    verify only). Kept as a real enum, not a boolean, so a future async gateway refund can report
    PENDING/FAILED later without a schema change.
    """

    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class Payment(TimeStampedModel):
    """
    One row per order — an order is either settled or it isn't, so multiple collection events (a
    partial Cash-on-Delivery payment now, the rest later) update this one row rather than adding
    another (see `services` for exactly how).

    `amount` is what is owed. While nothing has been collected yet it is kept equal to the order's
    `grand_total` (a signal on `Order`, see `signals.py`); once money has moved it is frozen, so an
    unrelated later edit to a pending order can never rewrite a payment that has already happened.
    `amount_received` is what has actually come in. `status` mirrors `Order.payment_status`
    (`services._sync_order` keeps them equal) — Module 10 declared that field but left it to this
    app to maintain, exactly as documented there.
    """

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    method = models.CharField(max_length=10, choices=PaymentMethod.choices)
    gateway = models.CharField(
        max_length=30, blank=True, help_text="Which gateway is handling this payment, e.g. 'stub'. Blank for Cash on Delivery."
    )
    status = models.CharField(max_length=15, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID, db_index=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[_min_zero])
    amount_received = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[_min_zero])
    transaction_id = models.CharField(max_length=100, blank=True, db_index=True, help_text="The gateway's own id/reference for this payment.")
    gateway_payload = models.JSONField(default=dict, blank=True, help_text="Raw initiate/callback/verify data, kept for debugging.")

    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Staff who last recorded money received (e.g. COD collected).",
    )
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="payment_amount_gte_0"),
            models.CheckConstraint(condition=Q(amount_received__gte=0), name="payment_received_gte_0"),
            models.CheckConstraint(condition=Q(amount_received__lte=F("amount")), name="payment_received_lte_amount"),
        ]

    def __str__(self):
        return f"Payment for order {self.order_id}: {self.status}"


class Refund(models.Model):
    """A refund against a payment. `payment.refunds` is its full refund history."""

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=RefundStatus.choices, default=RefundStatus.COMPLETED)
    transaction_id = models.CharField(max_length=100, blank=True, help_text="The gateway's refund id, if it was processed there.")
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0), name="refund_amount_gt_0")]

    def __str__(self):
        return f"Refund of {self.amount} on payment {self.payment_id}"
