"""
Sending notifications (Module 16).

    notify(Event.ORDER_PLACED, email=order.email, phone=order.phone, context={...}, order=order)

For each channel with a recipient and an active template, the message is rendered, logged, and delivered:
  * normal messages go to Celery (`tasks.deliver_notification`), which retries a failed send with back-off;
  * a message carrying a secret (`secrets=` — a reset code, a generated password) is delivered right here, never via
    the broker, so the secret is never written anywhere: the log gets the body with the secret masked.
No recipient (no email / no phone) → that channel is simply skipped. Nothing here ever raises into the caller.

Email uses Django's EMAIL_BACKEND, SMS `apps.core.messaging` (SMS_BACKEND): console in dev, a real provider in prod
by changing the setting only.
"""

import logging
import re

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.core.messaging import send_sms

from .models import Channel, Event, LogStatus, NotificationLog, NotificationTemplate

logger = logging.getLogger(__name__)

MASK = "••••••"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def max_attempts():
    return getattr(settings, "NOTIFICATION_MAX_ATTEMPTS", 3)


# --- templates -----------------------------------------------------------------------------------------------------------

# Placeholders each event provides (the template editor lists them; unknown ones are rejected). Secrets marked.
PLACEHOLDERS = {
    Event.ORDER_PLACED: ["site_name", "customer_name", "order_number", "total", "items", "payment_method", "address"],
    Event.ORDER_STATUS: ["site_name", "customer_name", "order_number", "total", "status", "tracking"],
    Event.PASSWORD_RESET: ["site_name", "code", "minutes"],
    Event.NEW_ACCOUNT: ["site_name", "customer_name", "login", "email", "password"],
    Event.LOW_STOCK: ["site_name", "product_name", "sku", "stock", "threshold"],
    Event.REVIEW_REPLY: ["site_name", "customer_name", "product_name", "reply"],
    Event.BACK_IN_STOCK: ["site_name", "product_name"],
}
SECRET_PLACEHOLDERS = {Event.PASSWORD_RESET: "code", Event.NEW_ACCOUNT: "password"}

# The built-in text, used until an Admin saves their own (NotificationTemplate). (event, channel): (subject, body).
DEFAULT_TEMPLATES = {
    (Event.ORDER_PLACED, Channel.SMS): ("", "Thank you {customer_name}! Your {site_name} order #{order_number} ({total}) has been placed. We'll confirm it soon."),
    (Event.ORDER_PLACED, Channel.EMAIL): (
        "Your {site_name} order #{order_number}",
        "Hello {customer_name},\n\nThank you for your order #{order_number}.\n\n{items}\n\nTotal: {total}\nPayment: {payment_method}\n"
        "Delivery address: {address}\n\nWe'll let you know as your order moves along.\n\n— {site_name}",
    ),
    (Event.ORDER_STATUS, Channel.SMS): ("", "{site_name}: your order #{order_number} is now {status}.{tracking}"),
    (Event.ORDER_STATUS, Channel.EMAIL): (
        "Order #{order_number}: {status}",
        "Hello {customer_name},\n\nYour order #{order_number} ({total}) is now: {status}.{tracking}\n\n— {site_name}",
    ),
    (Event.PASSWORD_RESET, Channel.SMS): ("", "Your {site_name} password reset code is {code}. It expires in {minutes} minutes. Do not share it."),
    (Event.PASSWORD_RESET, Channel.EMAIL): (
        "Your {site_name} password reset code",
        "Your {site_name} password reset code is {code}. It expires in {minutes} minutes. Do not share it.",
    ),
    (Event.NEW_ACCOUNT, Channel.EMAIL): (
        "Your {site_name} account details",
        "Hello {customer_name},\n\nThank you for your order. We created a {site_name} account so you can track it and order faster.\n\n"
        "  Login: {login}  (or {email})\n  Password: {password}\n\n"
        "You will be asked to change this password the first time you log in. "
        "If you ever forget it, use \"Forgot password\" on the login page.\n\n— {site_name}",
    ),
    (Event.LOW_STOCK, Channel.EMAIL): (
        "Low stock: {product_name}",
        "{product_name} (SKU {sku}) is down to {stock} in stock (alert level {threshold}).\n\nRestock it from the dashboard. — {site_name}",
    ),
    (Event.REVIEW_REPLY, Channel.EMAIL): (
        "We replied to your review",
        "Hello {customer_name},\n\nThank you for reviewing {product_name}. Our reply:\n\n\"{reply}\"\n\n— {site_name}",
    ),
    (Event.REVIEW_REPLY, Channel.SMS): ("", "{site_name} replied to your review of {product_name}: \"{reply}\""),
    (Event.BACK_IN_STOCK, Channel.SMS): ("", "Good news! {product_name} is back in stock at {site_name}. Order soon, stock is limited."),
}


def template_for(event, channel):
    """(subject, body) to send, or None when this event isn't sent on this channel (or the Admin switched it off)."""
    row = NotificationTemplate.objects.filter(event=event, channel=channel).first()
    if row is not None:
        return (row.subject, row.body) if row.is_active else None
    return DEFAULT_TEMPLATES.get((event, channel))


def render(text, values):
    """Fills {placeholders} from `values` by plain substitution (no format-string attribute access); unknown left as-is."""
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text or "")


def unknown_placeholders(event, *texts):
    allowed = set(PLACEHOLDERS.get(event, []))
    return sorted({name for text in texts for name in PLACEHOLDER.findall(text or "")} - allowed)


# --- sending -------------------------------------------------------------------------------------------------------------


def _site_name():
    from apps.site_settings.services import get_site_settings

    try:
        return get_site_settings().site_name
    except Exception:  # noqa: BLE001
        return "GalPal"


def notify(event, *, email=None, phone=None, context=None, secrets=None, order=None, user=None, inline=False):
    """Render, log and send `event` to whichever of `email` / `phone` is given. Returns the created logs."""
    logs = []
    try:
        base = {"site_name": _site_name(), **(context or {})}
        secrets = secrets or {}
        for channel, recipient in ((Channel.EMAIL, (email or "").strip()), (Channel.SMS, (phone or "").strip())):
            if not recipient:
                continue
            template = template_for(event, channel)
            if template is None:
                continue
            subject, body = template
            masked = {**base, **{key: MASK for key in secrets}}
            log = NotificationLog.objects.create(
                event=event, channel=channel, recipient=recipient,
                subject=render(subject, masked)[:200] if channel == Channel.EMAIL else "",
                body=render(body, masked), has_secret=bool(secrets), order=order, user=user,
            )
            logs.append(log)
            if secrets:
                real = {**base, **secrets}
                _deliver_inline(log, render(subject, real)[:200], render(body, real))
            elif inline:
                _deliver_inline(log)
            else:
                transaction.on_commit(lambda log_id=log.pk: _queue(log_id))
    except Exception:  # noqa: BLE001 - a notification problem must never break the action that triggered it
        logger.exception("Could not create the %s notification", event)
    return logs


def _queue(log_id):
    from .tasks import deliver_notification

    try:
        deliver_notification.delay(log_id)
    except Exception:  # noqa: BLE001 - broker down: send it now instead
        logger.warning("Notification queue unavailable; sending log %s inline", log_id)
        log = NotificationLog.objects.filter(pk=log_id).first()
        if log is not None:
            _deliver_inline(log)


def _deliver_inline(log, subject=None, body=None):
    """Up to `max_attempts()` tries right now (secret-bearing messages, and fallbacks)."""
    while log.status not in (LogStatus.SENT, LogStatus.FAILED):
        attempt(log, subject, body)


def attempt(log, subject=None, body=None):
    """
    One delivery try. `subject`/`body` are the real text when it differs from the logged (masked) one. Records the
    outcome on the log; after the last allowed failure the log is FAILED. Never raises. Returns True when sent.
    """
    log.attempts += 1
    try:
        if log.channel == Channel.EMAIL:
            send_mail(subject if subject is not None else log.subject, body if body is not None else log.body, None, [log.recipient], fail_silently=False)
        else:
            send_sms(log.recipient, body if body is not None else log.body)
    except Exception as exc:  # noqa: BLE001 - recorded on the log; the text is never logged (it may hold a secret)
        log.status = LogStatus.FAILED if log.attempts >= max_attempts() else LogStatus.RETRYING
        log.error = f"{type(exc).__name__}: {exc}"[:500]
        log.save(update_fields=["attempts", "status", "error", "updated_at"])
        logger.warning("Notification %s (%s %s) attempt %s failed", log.pk, log.event, log.channel, log.attempts)
        return False
    log.status, log.error, log.sent_at = LogStatus.SENT, "", timezone.now()
    log.save(update_fields=["attempts", "status", "error", "sent_at", "updated_at"])
    return True


def resend(log):
    """Admin "retry" on a failed log: a fresh round of attempts. Not possible for a message that held a secret."""
    from .exceptions import field_error

    if log.has_secret:
        raise field_error("log", "This message contained a code or password, so it can't be re-sent from the log.", "has_secret")
    if log.status == LogStatus.SENT:
        raise field_error("log", "This message was already sent.", "already_sent")
    log.status, log.attempts, log.error = LogStatus.QUEUED, 0, ""
    log.save(update_fields=["status", "attempts", "error", "updated_at"])
    transaction.on_commit(lambda: _queue(log.pk))
    return log


# --- the shop's notifications --------------------------------------------------------------------------------------------


def _money(value):
    from apps.site_settings.services import get_site_settings

    try:
        symbol = get_site_settings().currency_symbol
    except Exception:  # noqa: BLE001
        symbol = "৳"
    return f"{symbol}{value:,.2f}"


def _order_context(order):
    return {
        "customer_name": order.customer_name,
        "order_number": order.number,
        "total": _money(order.grand_total),
    }


def order_placed(order):
    items = "\n".join(
        f"  {item.quantity} × {item.product_name}{f' ({item.variant_label})' if item.variant_label else ''} — {_money(item.line_total)}"
        for item in order.items.all()
    )
    context = {
        **_order_context(order),
        "items": items,
        "payment_method": order.get_payment_method_display(),
        "address": ", ".join(part for part in (order.address_line, order.area, order.district) if part),
    }
    return notify(Event.ORDER_PLACED, email=order.email, phone=order.phone, context=context, order=order, user=order.customer)


def order_status_changed(order, new_status):
    from apps.orders.models import OrderStatus

    tracking = ""
    if new_status == OrderStatus.SHIPPED and (order.courier_name or order.tracking_id):
        tracking = " Courier: " + " · ".join(part for part in (order.courier_name, order.tracking_id) if part) + "."
    context = {**_order_context(order), "status": OrderStatus(new_status).label, "tracking": tracking}
    return notify(Event.ORDER_STATUS, email=order.email, phone=order.phone, context=context, order=order, user=order.customer)


def password_reset_code(user, code, *, by_email):
    context = {"minutes": settings.PASSWORD_RESET_OTP_TTL_MINUTES}
    return notify(
        Event.PASSWORD_RESET, email=user.email if by_email else None, phone=None if by_email else user.phone,
        context=context, secrets={"code": code}, user=user,
    )


def new_account(user, password):
    context = {"customer_name": user.full_name, "login": user.phone, "email": user.email or user.phone}
    return notify(Event.NEW_ACCOUNT, email=user.email, phone=user.phone, context=context, secrets={"password": password}, user=user)


def low_stock(product, variant, stock, threshold):
    from apps.accounts.models import User

    name = product.name
    if variant is not None:
        options = ", ".join(v.value for v in variant.attribute_values.all())
        name = f"{product.name} ({options})" if options else product.name
    context = {"product_name": name, "sku": (variant.sku if variant is not None and variant.sku else product.sku), "stock": stock, "threshold": threshold}
    logs = []
    for admin in User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(email=""):
        logs += notify(Event.LOW_STOCK, email=admin.email, context=context, user=admin)
    return logs


def review_reply(review):
    user = review.user
    if user is None:
        return []
    context = {"customer_name": review.reviewer_name or user.full_name, "product_name": review.product.name, "reply": review.admin_reply}
    return notify(Event.REVIEW_REPLY, email=user.email, phone=user.phone, context=context, user=user)


def back_in_stock(phone, product_name):
    """Inline: already called from a Celery task (catalog.tasks.send_restock_alerts_task). True when sent."""
    logs = notify(Event.BACK_IN_STOCK, phone=phone, context={"product_name": product_name}, inline=True)
    return bool(logs) and logs[0].status == LogStatus.SENT
