"""Customer care business logic (Module 14). Views only validate input and call these."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from apps.core.validators import normalize_bd_phone
from apps.orders.models import Order, OrderStatus

from .exceptions import field_error
from .models import (
    CheckoutLead,
    CheckoutLeadStatus,
    ContactMessage,
    ContactMessageNote,
    CustomerNote,
    CustomerTag,
    MessageStatus,
)

# Orders that never turned into a sale don't count towards "total spent".
NOT_SPENT = (OrderStatus.CANCELLED, OrderStatus.FAILED, OrderStatus.RETURNED)


# --- customer profile --------------------------------------------------------------------------------------------------


def customer_stats(user):
    """Order count, total spent (excluding cancelled/failed/returned orders) and last order time."""
    orders = Order.objects.filter(customer=user)
    stats = orders.aggregate(
        order_count=Count("id"),
        total_spent=Sum("grand_total", filter=~Q(status__in=NOT_SPENT)),
        last_order_at=Max("created_at"),
    )
    stats["total_spent"] = stats["total_spent"] or Decimal("0.00")
    return stats


def add_customer_note(customer, author, text):
    text = (text or "").strip()
    if not text:
        raise field_error("text", "Write a note.", "required")
    return CustomerNote.objects.create(customer=customer, author=author, text=text)


@transaction.atomic
def set_customer_tags(customer, names):
    """Replace a customer's tags with `names` (creating any tag that doesn't exist yet, case-insensitively)."""
    tags = []
    for raw in names:
        name = " ".join(str(raw).split())[:40]
        if not name:
            continue
        tag = CustomerTag.objects.filter(name__iexact=name).first() or CustomerTag.objects.create(name=name)
        tags.append(tag)
    customer.care_tags.set(tags)
    return tags


# --- support inbox -----------------------------------------------------------------------------------------------------


def submit_contact_message(*, data, user=None, ip_address=None):
    """A message from the public contact form. Needs a way to reply: a phone or an email."""
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip().lower()
    if not phone and not email:
        raise field_error("phone", "Give us a phone number or an email so we can reply.", "required")
    if phone:
        try:
            phone = normalize_bd_phone(phone)
        except Exception:  # noqa: BLE001 - the validator raises Django's ValidationError
            raise field_error("phone", "Enter a valid Bangladeshi mobile number, e.g. 01712345678.", "invalid") from None
    return ContactMessage.objects.create(
        name=data["name"].strip(), phone=phone, email=email, subject=(data.get("subject") or "").strip(),
        message=data["message"].strip(), user=user if user and user.is_authenticated else None, ip_address=ip_address,
    )


def add_message_note(message, author, text, *, status=None):
    """A working/reply note on a support message; optionally moves it to `status` at the same time."""
    text = (text or "").strip()
    if not text:
        raise field_error("text", "Write a note.", "required")
    with transaction.atomic():
        note = ContactMessageNote.objects.create(message=message, author=author, text=text)
        if status and status != message.status:
            message.status = status
            message.save(update_fields=["status", "updated_at"])
        elif message.status == MessageStatus.NEW:
            message.status = MessageStatus.IN_PROGRESS  # someone is on it
            message.save(update_fields=["status", "updated_at"])
    return note


# --- abandoned checkouts -----------------------------------------------------------------------------------------------


def _cart_snapshot(cart):
    if cart is None:
        return [], Decimal("0.00")
    from apps.cart import services as cart_services  # lazy: cart -> catalog -> … import chain

    summary = cart_services.summarize(cart)
    rows = [
        {"name": row["item"].product.name, "quantity": row["item"].quantity, "price": f"{row['unit_price']:.2f}"}
        for row in summary["rows"]
    ]
    return rows, summary["subtotal"]


@transaction.atomic
def capture_checkout_lead(*, phone, name="", email="", district="", user=None, cart=None):
    """
    Remember someone who reached checkout and typed their name and phone. One OPEN lead per phone: later captures
    update it (latest name/email/cart). Returns the lead. Never affects the cart or the order.
    """
    phone = normalize_bd_phone(phone)
    items, value = _cart_snapshot(cart)
    lead = CheckoutLead.objects.select_for_update().filter(phone=phone, status=CheckoutLeadStatus.OPEN).first()
    fields = {
        "name": (name or "").strip()[:150], "email": (email or "").strip().lower()[:254], "district": (district or "").strip()[:60],
        "user": user if user and user.is_authenticated else None, "cart_snapshot": items, "cart_value": value,
    }
    if lead is None:
        return CheckoutLead.objects.create(phone=phone, **fields)
    for key, value_ in fields.items():
        if value_ or key in ("cart_snapshot", "cart_value"):
            setattr(lead, key, value_)
    lead.save()
    return lead


def mark_leads_converted(order):
    """An order was placed with this phone: its open checkout lead isn't abandoned any more."""
    CheckoutLead.objects.filter(phone=order.phone, status=CheckoutLeadStatus.OPEN).update(
        status=CheckoutLeadStatus.CONVERTED, converted_order=order, updated_at=timezone.now(),
    )


def abandoned_checkouts(now=None):
    """Open leads untouched for at least CHECKOUT_ABANDON_MINUTES (someone still typing isn't abandoned yet)."""
    minutes = getattr(settings, "CHECKOUT_ABANDON_MINUTES", 30)
    cutoff = (now or timezone.now()) - timedelta(minutes=minutes)
    return CheckoutLead.objects.filter(status=CheckoutLeadStatus.OPEN, updated_at__lte=cutoff).select_related("user")
