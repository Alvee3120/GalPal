"""
Payment business logic: recording money against an order (Cash on Delivery or a gateway), refunds,
and keeping `Order.payment_status` in sync.

`Payment` is one-to-one with `Order`, auto-created the moment an order is placed (a signal on
`Order`, see `signals.py`) — Module 10's checkout / manual-order code is never touched; this app
only maintains a field it already owned by design (`Order.payment_status`).

Money is never double-counted: a gateway success (callback or `verify`) *sets* `amount_received` to
whatever the gateway reports, which is safe under webhook retries, while an admin's `mark_received`
(a real, one-off action, not a machine retry) *adds* to it.
"""
import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction

from apps.catalog.exceptions import Conflict
from apps.orders.models import PaymentStatus

from . import gateways
from .exceptions import field_error
from .models import Payment, Refund, RefundStatus

logger = logging.getLogger(__name__)
CENTS = Decimal("0.01")


def _money(value, field_name="amount"):
    try:
        amount = Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise field_error(field_name, "A valid amount is required.", "invalid") from None
    if not amount.is_finite() or amount <= 0:
        raise field_error(field_name, "The amount must be greater than zero.", "invalid_amount")
    return amount


def refunded_total(payment):
    return sum((r.amount for r in payment.refunds.filter(status=RefundStatus.COMPLETED)), Decimal("0.00"))


def net_received(payment):
    """What is left of the money collected, after refunds."""
    return payment.amount_received - refunded_total(payment)


def _sync_order(payment):
    order = payment.order
    if order.payment_status != payment.status:
        order.payment_status = payment.status
        order.save(update_fields=["payment_status", "updated_at"])


def _recompute_status(payment):
    if payment.amount_received <= 0:
        return PaymentStatus.UNPAID
    if net_received(payment) <= 0:
        return PaymentStatus.REFUNDED
    if payment.amount_received >= payment.amount:
        return PaymentStatus.PAID
    return PaymentStatus.PARTIALLY_PAID


@transaction.atomic
def mark_received(payment, *, amount=None, note="", user=None):
    """
    Record money actually collected — typically Cash on Delivery. `amount` defaults to whatever is
    still owed. Safe to call more than once: each call adds to what's already been recorded, for a
    customer who pays in more than one instalment.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    remaining = payment.amount - payment.amount_received
    if remaining <= 0:
        raise Conflict("The full amount has already been collected on this payment.", code="already_collected")
    amount = _money(amount) if amount is not None else remaining
    if amount > remaining:
        raise field_error("amount", f"Only {remaining} is still owed on this order.", "exceeds_amount_due")
    payment.amount_received += amount
    payment.status = _recompute_status(payment)
    payment.collected_by = user if user and user.pk else None
    payment.note = note
    payment.save(update_fields=["amount_received", "status", "collected_by", "note", "updated_at"])
    _sync_order(payment)
    return payment


def _get_gateway_or_400(slug):
    try:
        return gateways.get_gateway(slug)
    except gateways.GatewayError as exc:
        raise field_error("gateway", exc.message, exc.code) from None


@transaction.atomic
def initiate_payment(payment, *, gateway_slug=None, user=None):
    """
    Start a gateway charge for `payment`. Not restricted to `method="online"` — an admin may want to
    send a customer a payment link for an order that was placed as Cash on Delivery.
    """
    from django.conf import settings

    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status in (PaymentStatus.PAID, PaymentStatus.REFUNDED):
        raise Conflict("This payment is already settled.", code="already_settled")
    slug = gateway_slug or settings.DEFAULT_PAYMENT_GATEWAY
    gateway = _get_gateway_or_400(slug)
    result = gateway.initiate(payment)
    payment.gateway = slug
    payment.transaction_id = result.reference
    payment.gateway_payload = {**(payment.gateway_payload or {}), "last_initiate": result.raw}
    payment.save(update_fields=["gateway", "transaction_id", "gateway_payload", "updated_at"])
    return payment, result


@transaction.atomic
def verify_payment(payment, *, user=None):
    """Ask the gateway directly what this payment's status is (a missed webhook, reconciliation)."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if not payment.gateway:
        raise Conflict("This payment has no gateway to verify against.", code="no_gateway")
    result = gateways.get_gateway(payment.gateway).verify(payment)
    _apply_gateway_result(payment, result)
    return payment


@transaction.atomic
def handle_callback(gateway_slug, raw_body, headers):
    """The IPN/webhook entry point. The gateway proves itself with a signature, so this needs no
    authentication of its own — exactly like a real payment provider's callback."""
    gateway = _get_gateway_or_400(gateway_slug)
    try:
        result = gateway.parse_callback(raw_body, headers)
    except gateways.InvalidSignature as exc:
        raise field_error("signature", exc.message, exc.code) from None
    except gateways.GatewayError as exc:
        raise field_error("payload", exc.message, exc.code) from None
    payment = Payment.objects.select_for_update().filter(gateway=gateway_slug, transaction_id=result.reference).first()
    if payment is None:
        raise field_error("reference", "No payment matches this reference.", "unknown_reference")
    _apply_gateway_result(payment, result)
    return payment


def _apply_gateway_result(payment, result):
    """
    Shared by `verify_payment` and `handle_callback`: idempotent under webhook retries (it SETS
    `amount_received` rather than adding to it), and a stray "failed" can never erase an earlier
    success — the last thing that actually happened.
    """
    payload = dict(payment.gateway_payload or {})
    payload["last_callback"] = {
        "reference": result.reference, "status": result.outcome,
        "amount": str(result.amount) if result.amount is not None else None, **result.raw,
    }
    payment.gateway_payload = payload
    if result.outcome == "success":
        amount = result.amount if result.amount is not None else payment.amount
        if amount <= 0:
            raise field_error("amount", "A successful payment must report a positive amount.", "invalid_amount")
        payment.amount_received = amount
        payment.status = _recompute_status(payment)
    elif result.outcome == "failed" and payment.amount_received <= 0:
        payment.status = PaymentStatus.FAILED
    payment.save(update_fields=["gateway_payload", "amount_received", "status", "updated_at"])
    _sync_order(payment)


@transaction.atomic
def create_refund(payment, *, amount, reason, user, transaction_id=""):
    """Record a refund. Currently always immediate/admin-declared (see `Refund`/`RefundStatus`)."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    available = net_received(payment)
    if available <= 0:
        raise Conflict("There is nothing to refund on this payment.", code="nothing_to_refund")
    amount = _money(amount)
    if amount > available:
        raise field_error("amount", f"Only {available} can be refunded.", "exceeds_refundable")
    reason = (reason or "").strip()
    if not reason:
        raise field_error("reason", "A reason is required.", "reason_required")

    refund = Refund.objects.create(
        payment=payment, amount=amount, reason=reason[:255], status=RefundStatus.COMPLETED,
        transaction_id=transaction_id, processed_by=user if user and user.pk else None,
    )
    payment.status = _recompute_status(payment)
    payment.save(update_fields=["status", "updated_at"])
    _sync_order(payment)
    return refund
