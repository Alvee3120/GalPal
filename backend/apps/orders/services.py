"""
Order business logic: placing an order (storefront checkout and staff-entered), editing a pending
order, status changes, cancellation, the Admin's shipping override, and lookups.

Rules that hold everywhere in this module
-----------------------------------------
* Everything runs in one `transaction.atomic()`. Any failure (stock, coupon, account creation,
  an unexpected error) leaves no order, no stock change and no coupon usage behind.
* Nothing money-related comes from the client. Prices come from the catalog, the shipping charge
  from Module 9's `calculate_shipping`, the discount from Module 8, tax from Site Settings; all are
  copied onto the order as a snapshot.
* Stock is **deducted when the order is placed** and put back on cancel / fail / return, using the
  amounts each line really took (`OrderItem.stock_deducted`), so a restore is exact even for
  backorder lines and can happen only once (`Order.stock_released_at`).
* Lock order is always: phone (advisory) -> product/variant rows sorted by id -> the coupon row (locked
  inside `redeem_coupon`, which is the authoritative limit check) -> the order row for later changes. A
  fixed order is what keeps concurrent orders from deadlocking.
"""
import hashlib
import logging
import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, Throttled

from apps.accounts.exceptions import AccountAlreadyExists
from apps.accounts.models import User
from apps.accounts.services import create_customer_account
from apps.cart import services as cart_services
from apps.cart.models import CartItem
from apps.catalog import services as catalog_services
from apps.catalog.exceptions import Conflict
from apps.catalog.models import Product, ProductVariant, StockMovement
from apps.coupons import services as coupon_services
from apps.coupons.models import Coupon, CouponUsage
from apps.shipping import services as shipping_services
from apps.site_settings.services import get_site_settings

from . import notifications
from .exceptions import field_error
from .models import Order, OrderItem, OrderNote, OrderStatus, OrderStatusHistory, PaymentMethod

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")
S = OrderStatus

# --- the status machine ---------------------------------------------------------------------------------

# Staff may move an order from any status to any other (e.g. to correct a mistake or reopen a cancelled
# order); change_status keeps stock and coupon usage in step with whichever way the order moves.
TRANSITIONS = {old: {new for new in S if new != old} for old in S}
STOCK_RELEASING = {S.CANCELLED, S.FAILED, S.RETURNED}  # the goods never left, or came back
COUPON_RELEASING = {S.CANCELLED, S.FAILED}  # a coupon isn't "used" by an order that never happened
CUSTOMER_CANCELLABLE = {S.PENDING}  # once staff confirms an order, the customer can no longer cancel it themselves
OVERRIDABLE_SHIPPING = {S.PENDING, S.CONFIRMED, S.PROCESSING}  # before it has shipped
DELETABLE = {S.CANCELLED, S.FAILED, S.RETURNED}
INACTIVE_FOR_GUARDS = [S.CANCELLED, S.FAILED]  # such orders don't count as "duplicates" or "previous orders"

ADDRESS_FIELDS = ("division", "district", "area", "address_line", "postal_code")
CONTACT_FIELDS = ("customer_name", "phone", "email")


@dataclass
class ResolvedLine:
    product: Product
    variant: ProductVariant | None
    quantity: int
    unit_price: Decimal
    regular_price: Decimal
    deduct: int  # units to take from stock
    product_name: str
    sku: str
    variant_label: str
    image: str

    @property
    def line_total(self):
        return self.unit_price * self.quantity


@dataclass
class PlacedOrder:
    order: Order
    account_created: bool = False
    warnings: list = field(default_factory=list)


# --- small helpers ---------------------------------------------------------------------------------------


def _money(value):
    return Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def new_order_number():
    """e.g. GP-260921-7K3F: readable over the phone, and not a counter anyone can walk through."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
    return f"GP-{timezone.localdate():%y%m%d}-" + "".join(secrets.choice(alphabet) for _ in range(4))


def _lock_phone(*phones):
    """
    Serialise all order work for a phone number (until the transaction ends). This is what makes
    the duplicate check, the hourly limit and "first order only" race-free: two simultaneous orders
    from one phone run one after the other instead of both passing the same check.
    """
    with connection.cursor() as cursor:
        for phone in sorted({p for p in phones if p}):
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"order-phone:{phone}"])


def _fingerprint(phone, entries):
    raw = phone + "|" + ";".join(f"{pid}:{vid or 0}:{qty}" for (pid, vid), qty in entries)
    return hashlib.sha256(raw.encode()).hexdigest()


def consolidate(lines):
    """Merge repeated products/variants and return `[((product_id, variant_id), quantity), ...]`, sorted."""
    merged = {}
    for line in lines:
        key = (int(line["product_id"]), int(line["variant_id"]) if line.get("variant_id") else None)
        merged[key] = merged.get(key, 0) + int(line["quantity"])
    return sorted(merged.items(), key=lambda pair: (pair[0][0], pair[0][1] or 0))


def _variant_label(variant):
    if variant is None:
        return ""
    values = variant.attribute_values.select_related("attribute").order_by("attribute__name", "value")
    return " / ".join(f"{v.attribute.name}: {v.value}" for v in values)


def _has_previous_orders(customer, phone):
    who = Q(phone=phone) | (Q(customer=customer) if customer is not None else Q())
    return Order.objects.filter(who).exclude(status__in=INACTIVE_FOR_GUARDS).exists()


# --- resolving what is being bought -------------------------------------------------------------------------


def resolve_lines(entries):
    """
    Lock and check every product/variant in `entries` (already sorted) and price it from the catalog.
    All problems are collected and raised together under `items`, so the client can show each one.
    """
    resolved, problems = [], []
    for (product_id, variant_id), quantity in entries:
        product = Product.objects.select_for_update().filter(pk=product_id).first()
        if product is None:
            problems.append(f"Product {product_id} is not available.")
            continue
        variant = None
        if variant_id is not None:
            variant = ProductVariant.objects.select_for_update().filter(pk=variant_id).first()
            if variant is None:
                problems.append(f"{product.name}: this variant is not available.")
                continue
        try:
            cart_services._assert_addable(product, variant)  # published, variant belongs/active, variant needed or not
        except ValidationError as exc:
            problems.append(f"{product.name}: {next(iter(exc.message_dict.values()))[0]}")
            continue

        target = variant or product
        cap = cart_services.available_quantity(target)  # None: stock isn't managed or backorder
        if cap is not None and quantity > cap:
            problems.append(f"{product.name}: only {cap} left in stock." if cap else f"{product.name}: out of stock.")
            continue
        if not target.manage_stock:
            deduct = 0
        elif cap is None:  # backorder: sell past zero, but only ever take what is on the shelf
            deduct = min(quantity, target.stock_quantity)
        else:
            deduct = quantity
        image = (variant.image if variant and variant.image else product.feature_image)
        resolved.append(ResolvedLine(
            product=product, variant=variant, quantity=quantity, unit_price=target.effective_price,
            regular_price=variant.regular_price_effective if variant else product.regular_price, deduct=deduct,
            product_name=product.name, sku=variant.sku if variant else product.sku,
            variant_label=_variant_label(variant), image=image.name if image else "",
        ))
    if problems:
        raise ValidationError({"items": problems})
    return resolved


def _coupon_rows(lines):
    """The row shape Module 8's coupon code evaluates, built from lines that aren't in any cart."""
    return [
        {"item": CartItem(product=l.product, variant=l.variant, quantity=l.quantity), "unit_price": l.unit_price,
         "line_total": l.line_total, "is_available": True, "available_quantity": None}
        for l in lines
    ]


def _tax(subtotal, discount):
    percent = get_site_settings().tax_percent or Decimal("0")
    return percent, _money((subtotal - discount) * percent / Decimal("100"))


def _apply_shipping(order, quote):
    order.shipping_zone_id = quote["zone_id"]
    order.shipping_zone_name = quote["zone_name"]
    method = quote["delivery_method"]
    order.delivery_method_id = method["id"] if method else None
    order.delivery_method_name = method["name"] if method else ""
    order.shipping_charge = quote["charge"]
    order.shipping_free_reason = quote["free_shipping_reason"] or ""
    order.shipping_overridden = False
    order.shipping_override_reason = ""


def _recalculate_total(order):
    order.grand_total = order.subtotal - order.discount_amount + order.shipping_charge + order.tax_amount


# --- stock ------------------------------------------------------------------------------------------------------


def _deduct_stock(order, lines, user):
    for line in lines:
        if line.deduct:
            catalog_services.adjust_stock(
                product=line.product, variant=line.variant, quantity_change=-line.deduct,
                reason=StockMovement.Reason.SALE, reference=order.number, note="Order placed", user=user,
            )


def _restore_stock(order, note, user):
    """Put back exactly what each line took. Once only. Skips lines whose product is gone or no longer tracks stock."""
    if order.stock_released_at is not None:
        return
    for item in order.items.select_related("product", "variant"):
        if not item.stock_deducted or item.product is None:
            continue
        try:
            catalog_services.adjust_stock(
                product=item.product, variant=item.variant, quantity_change=item.stock_deducted,
                reason=StockMovement.Reason.RETURN, reference=order.number, note=note, user=user,
            )
        except ValidationError:  # stock stopped being managed since; nothing to restore into
            logger.warning("Could not restore stock for order %s item %s", order.number, item.pk)
    order.stock_released_at = timezone.now()
    order.save(update_fields=["stock_released_at", "updated_at"])


def _retake_stock(order, note, user):
    """Undo `_restore_stock` for an order that is live again: take each line's stock_deducted back off the shelf."""
    if order.stock_released_at is None:
        return
    for item in order.items.select_related("product", "variant"):
        if not item.stock_deducted or item.product is None:
            continue
        target = item.variant or item.product
        if not target.manage_stock:
            continue
        try:
            catalog_services.adjust_stock(
                product=item.product, variant=item.variant, quantity_change=-item.stock_deducted,
                reason=StockMovement.Reason.SALE, reference=order.number, note=note, user=user,
            )
        except ValidationError:
            name = f"{item.product_name} ({item.variant_label})" if item.variant_label else item.product_name
            raise field_error("status", f"Not enough stock to reopen this order: {name} needs {item.stock_deducted}.", "insufficient_stock")
    order.stock_released_at = None
    order.save(update_fields=["stock_released_at", "updated_at"])


def _persist_items(order, lines):
    OrderItem.objects.bulk_create([
        OrderItem(
            order=order, product=l.product, variant=l.variant, product_name=l.product_name, sku=l.sku,
            variant_label=l.variant_label, image=l.image, regular_price=l.regular_price, unit_price=l.unit_price,
            quantity=l.quantity, line_total=l.line_total, stock_deducted=l.deduct,
        )
        for l in lines
    ])


# --- abuse guards ---------------------------------------------------------------------------------------------------


def _check_abuse(phone, fingerprint, *, is_manual, warnings):
    """
    Storefront: refuse a repeat of the same order (same phone + same items) within a few minutes and
    cap how many orders one phone can place per hour. Staff-entered orders only get a warning: a
    customer may genuinely ring twice, and the CCE can see the earlier order number.
    """
    now = timezone.now()
    window = now - timedelta(seconds=settings.ORDER_DUPLICATE_WINDOW_SECONDS)
    duplicate = (
        Order.objects.filter(fingerprint=fingerprint, created_at__gte=window)
        .exclude(status__in=INACTIVE_FOR_GUARDS).order_by("-created_at").first()
    )
    if is_manual:
        if duplicate:
            minutes = max(int((now - duplicate.created_at).total_seconds() // 60), 0)
            warnings.append(
                f"A similar order for this phone with the same items ({duplicate.number}) was placed {minutes} minute(s) ago."
            )
        return
    if duplicate:
        raise Conflict(
            "You have just placed this same order. Please wait a few minutes before ordering the same items again.",
            code="duplicate_order",
        )
    recent = Order.objects.filter(phone=phone, is_manual=False, created_at__gte=now - timedelta(hours=1)).count()
    if recent >= settings.ORDER_MAX_PER_PHONE_PER_HOUR:
        raise Throttled(wait=3600, detail="Too many orders from this phone number. Please try again later.")


# --- placing an order --------------------------------------------------------------------------------------------------


def _create_order(
    *, lines, contact, address, source, payment_method, note="", coupon_code="", coupon_is_optional=False,
    delivery_method="", customer=None, created_by=None, is_manual=False, source_note="", ip_address=None,
    min_order_amount=None, create_account=False,
):
    """The one place an order row is built. Must run inside a transaction (the two entry points below do)."""
    warnings = []
    phone = contact["phone"]
    _lock_phone(phone)

    entries = consolidate(lines)
    fingerprint = _fingerprint(phone, entries)
    _check_abuse(phone, fingerprint, is_manual=is_manual, warnings=warnings)

    coupon = None
    if coupon_code:
        coupon = Coupon.objects.filter(code=coupon_code.strip().upper()).first()
        if coupon is None and not coupon_is_optional:
            raise field_error("coupon", "Invalid coupon code.", "not_found")

    resolved = resolve_lines(entries)
    subtotal = sum((l.line_total for l in resolved), Decimal("0.00"))
    if min_order_amount and subtotal < min_order_amount:
        raise field_error("items", f"The minimum order amount is {_money(min_order_amount)}.", "min_order_amount")

    discount = Decimal("0.00")
    if coupon is not None:
        valid, message, discount = coupon_services.evaluate(
            coupon, subtotal=subtotal, rows=_coupon_rows(resolved), user=customer, phone=phone
        )
        if valid and coupon.first_order_only and _has_previous_orders(customer, phone):
            valid, message = False, "This coupon is only for a customer's first order."
        if not valid:
            if not coupon_is_optional:
                raise field_error("coupon", message, "coupon_not_applicable")
            coupon, discount = None, Decimal("0.00")  # a cart coupon that stopped applying is dropped, not an error

    quote = shipping_services.calculate_shipping(address, subtotal, coupon, delivery_method=delivery_method or None)
    tax_percent, tax_amount = _tax(subtotal, discount)

    order = Order(
        customer=customer, customer_name=contact["customer_name"], phone=phone, email=contact.get("email", ""),
        note=note, source=source, source_note=source_note, is_manual=is_manual, created_by=created_by,
        payment_method=payment_method, subtotal=subtotal, discount_amount=discount, coupon=coupon,
        coupon_code=coupon.code if coupon else "", tax_percent=tax_percent, tax_amount=tax_amount,
        fingerprint=fingerprint, ip_address=ip_address, **{name: address.get(name, "") for name in ADDRESS_FIELDS},
    )
    _apply_shipping(order, quote)
    _recalculate_total(order)
    _save_with_unique_number(order)
    _persist_items(order, resolved)
    OrderStatusHistory.objects.create(
        order=order, from_status="", to_status=S.PENDING, changed_by=created_by or customer,
        note="Order placed by staff" if is_manual else "Order placed",
    )
    _deduct_stock(order, resolved, created_by or customer)
    if coupon is not None:
        coupon_services.redeem_coupon(
            coupon, phone=phone, order_reference=order.number, discount_amount=discount, user=customer
        )

    account_created = False
    if create_account:
        account_created = _create_account_for(order, address)
    return PlacedOrder(order=order, account_created=account_created, warnings=warnings)


def _save_with_unique_number(order):
    for _ in range(10):
        order.number = new_order_number()
        if Order.all_objects.filter(number=order.number).exists():
            continue
        try:
            with transaction.atomic():
                order.save()
            return
        except IntegrityError:
            if not Order.all_objects.filter(number=order.number).exists():
                raise  # a different constraint failed; don't hide it behind a retry
    raise RuntimeError("Could not allocate an order number")


def _create_account_for(order, address):
    """
    Guest checkout with "save my details": make the customer an account and link the order to it.
    If the phone or email already belongs to someone we do nothing and say nothing: the order stays a
    plain guest order and the caller can't tell an account exists. The generated password only ever
    leaves this function inside the after-commit email.
    """
    try:
        new = create_customer_account(
            order.customer_name, order.phone, order.email, address={k: v for k, v in address.items() if k in ADDRESS_FIELDS},
        )
    except AccountAlreadyExists:
        return False
    order.customer = new.user
    order.save(update_fields=["customer", "updated_at"])
    user, password = new.user, new.password
    transaction.on_commit(lambda: notifications.send_new_account_email(user, password))
    return True


def checkout(*, cart, user, data, ip_address=None):
    """
    Storefront checkout for a customer or a guest, from their cart. `data` is the validated checkout
    payload (see `CheckoutSerializer`). The order's source is always `website`, whatever the client sent.
    """
    is_guest = user is None
    site = get_site_settings()
    if is_guest and not site.guest_checkout_enabled:
        raise PermissionDenied(detail="Guest checkout is turned off. Please log in to place an order.", code="guest_checkout_disabled")
    if data["payment_method"] not in settings.ENABLED_PAYMENT_METHODS:
        raise field_error("payment_method", "This payment method is not available.", "payment_method_unavailable")

    all_items = list(cart.items.select_related("product", "variant")) if cart is not None else []
    if not all_items:
        raise field_error("cart", "Your cart is empty.", "cart_empty")

    # Only items the cart itself currently considers available are eligible for the order — the same live
    # check cart_services.summarize() uses to decide what counts toward the cart's own subtotal, so a line
    # that's already excluded from what the customer sees they'll pay for is never silently ordered either.
    # An out-of-stock/unavailable line is skipped, not allowed to fail the whole checkout, and is left in
    # the cart afterward instead of being deleted with the rest.
    items = [item for item in all_items if cart_services.line_price(item)[1]]
    if not items:
        raise field_error("cart", "All items in your cart are currently out of stock.", "cart_all_unavailable")

    # "Save my details" only means anything for a guest, and only while the store allows it.
    create_account = bool(is_guest and data.get("save_details") and site.allow_checkout_account_creation)
    if create_account and not data.get("email"):
        raise field_error("email", "An email address is required to save your details.", "email_required")

    typed_code = data.get("coupon") or ""
    with transaction.atomic():
        placed = _create_order(
            lines=[{"product_id": i.product_id, "variant_id": i.variant_id, "quantity": i.quantity} for i in items],
            contact={"customer_name": data["name"], "phone": data["phone"], "email": data.get("email", "")},
            address={name: data.get(name, "") for name in ADDRESS_FIELDS},
            source="website", payment_method=data["payment_method"], note=data.get("note", ""),
            coupon_code=typed_code or (cart.coupon.code if cart.coupon_id else ""),
            coupon_is_optional=not typed_code, delivery_method=data.get("delivery_method", ""),
            customer=user, ip_address=ip_address, min_order_amount=site.min_order_amount, create_account=create_account,
        )
        # Only the lines that actually became order items leave the cart; anything skipped for being
        # unavailable stays, exactly as it was, for the customer to see or remove themselves.
        cart.items.filter(pk__in=[i.pk for i in items]).delete()
        if cart.coupon_id:
            cart.coupon = None
            cart.save(update_fields=["coupon", "updated_at"])
    return placed


def create_manual_order(*, staff, data):
    """
    A phone/social order entered by a CCE or Admin. `source` is chosen by the staff member; the shipping
    charge is always resolved from the address (staff can't type one); no account is ever created.
    """
    with transaction.atomic():
        return _create_order(
            lines=data["items"],
            contact={"customer_name": data["name"], "phone": data["phone"], "email": data.get("email", "")},
            address={name: data.get(name, "") for name in ADDRESS_FIELDS},
            source=data["source"], source_note=data.get("source_note", ""), payment_method=data["payment_method"],
            note=data.get("note", ""), coupon_code=data.get("coupon") or "", delivery_method=data.get("delivery_method", ""),
            customer=data.get("customer"), created_by=staff, is_manual=True,
        )


# --- editing a pending order -------------------------------------------------------------------------------------


def _describe_item_changes(old_items, new_lines):
    """A short, human-readable diff between an order's old items and its newly-resolved lines, for the
    "Order edited: items (...)" history note (see update_order) — so the timeline says what actually changed,
    not just that "items" changed."""
    def label(name, variant_label):
        return f"{name} ({variant_label})" if variant_label else name

    old_by_key = {(i.product_id, i.variant_id): i for i in old_items}
    new_by_key = {(l.product.id, l.variant.id if l.variant else None): l for l in new_lines}

    parts = []
    for key, line in new_by_key.items():
        old = old_by_key.get(key)
        name = label(line.product_name, line.variant_label)
        if old is None:
            parts.append(f"added {name} x{line.quantity}")
        elif old.quantity != line.quantity:
            parts.append(f"{name} x{old.quantity} -> x{line.quantity}")
    for key, item in old_by_key.items():
        if key not in new_by_key:
            parts.append(f"removed {label(item.product_name, item.variant_label)} x{item.quantity}")
    return ", ".join(parts)


@transaction.atomic
def update_order(order, *, user, data):
    """
    Edit a *pending* order's contact, address, delivery method or items and recalculate everything
    atomically: subtotal, coupon discount (kept while it still applies), shipping (re-resolved from the
    new address at today's zone charge, which also clears any Admin override), tax and total. Stock for
    the old lines is put back and the new lines are taken, all or nothing.
    """
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != S.PENDING:
        raise Conflict("Only a pending order can be edited.", code="order_not_editable")
    new_phone = data.get("phone", order.phone)
    _lock_phone(order.phone, new_phone)

    changes = []
    for name in (*CONTACT_FIELDS, *ADDRESS_FIELDS, "note"):
        if name in data and data[name] != getattr(order, name):
            setattr(order, name, data[name])
            changes.append(name)

    items_changed = "items" in data
    if items_changed:
        old_items = list(order.items.all())
        _restore_stock(order, f"Order {order.number} edited", user)
        order.stock_released_at = None  # the order is live again with its new lines
        order.items.all().delete()
        entries = consolidate(data["items"])
        lines = resolve_lines(entries)
        _persist_items(order, lines)
        _deduct_stock(order, lines, user)
        order.fingerprint = _fingerprint(order.phone, entries)
        item_summary = _describe_item_changes(old_items, lines)
        changes.append(f"items ({item_summary})" if item_summary else "items")
    elif "phone" in changes:
        entries = [((i.product_id, i.variant_id), i.quantity) for i in order.items.all() if i.product_id]
        order.fingerprint = _fingerprint(order.phone, sorted(entries, key=lambda p: (p[0][0], p[0][1] or 0)))

    kept = list(order.items.select_related("product", "variant"))
    order.subtotal = sum((i.line_total for i in kept), Decimal("0.00"))

    coupon = order.coupon
    if data.get("remove_coupon") and coupon is not None:
        CouponUsage.objects.filter(order_reference=order.number).delete()
        order.coupon, order.coupon_code, order.discount_amount, coupon = None, "", Decimal("0.00"), None
        changes.append("coupon removed")
    if coupon is not None:
        rows = [
            {"item": CartItem(product=i.product, variant=i.variant, quantity=i.quantity), "unit_price": i.unit_price,
             "line_total": i.line_total, "is_available": True, "available_quantity": None}
            for i in kept if i.product is not None
        ]
        if order.subtotal < coupon.min_order_amount:
            raise field_error("items", f"The order's coupon needs a minimum of {coupon.min_order_amount}. Remove the coupon first.", "coupon_no_longer_applies")
        discount = coupon_services.compute_discount(coupon, rows)
        if discount <= 0:
            raise field_error("items", "The order's coupon no longer applies to these items. Remove the coupon first.", "coupon_no_longer_applies")
        order.discount_amount = discount
        CouponUsage.objects.filter(order_reference=order.number).update(discount_amount=discount)

    if "delivery_method" in data:
        method_slug = data["delivery_method"] or None
    else:
        method_slug = order.delivery_method.slug if order.delivery_method_id else None
    quote = shipping_services.calculate_shipping(
        {"district": order.district, "area": order.area}, order.subtotal, coupon, delivery_method=method_slug
    )
    if order.shipping_overridden:
        changes.append("shipping override cleared")
    _apply_shipping(order, quote)
    order.tax_percent, order.tax_amount = _tax(order.subtotal, order.discount_amount)
    _recalculate_total(order)
    order.save()

    if changes:
        OrderStatusHistory.objects.create(
            order=order, from_status=order.status, to_status=order.status, changed_by=user,
            note="Order edited: " + ", ".join(changes),
        )
    return order


# --- status changes ---------------------------------------------------------------------------------------------------


def allowed_transitions(status):
    return sorted(TRANSITIONS.get(status, ()))


@transaction.atomic
def change_status(order, new_status, *, user, note="", courier=None):
    """
    Move an order to another status and log it. Cancel/fail/return put the stock back (and cancel/fail free the
    coupon use); moving such an order back to a live status takes the stock and the coupon use again.
    """
    order = Order.objects.select_for_update().get(pk=order.pk)
    old = order.status
    if new_status == old:
        raise field_error("status", f"The order is already {old}.", "same_status")
    if new_status not in TRANSITIONS[old]:
        allowed = ", ".join(allowed_transitions(old)) or "none (it is final)"
        raise field_error("status", f"An order that is {old} can't become {new_status}. Allowed: {allowed}.", "invalid_transition")

    order.status = new_status
    for name, value in (courier or {}).items():
        if value:
            setattr(order, name, value)
    order.save()
    if new_status in STOCK_RELEASING:
        _restore_stock(order, f"Order {new_status}", user)
    else:
        _retake_stock(order, f"Order reopened as {new_status}", user)
    if new_status in COUPON_RELEASING:
        CouponUsage.objects.filter(order_reference=order.number).delete()
    elif old in COUPON_RELEASING and order.coupon_id and order.discount_amount:
        CouponUsage.objects.get_or_create(
            order_reference=order.number,
            defaults={"coupon_id": order.coupon_id, "user": order.customer, "phone": order.phone, "discount_amount": order.discount_amount},
        )
    OrderStatusHistory.objects.create(order=order, from_status=old, to_status=new_status, changed_by=user, note=note)
    return order


@transaction.atomic
def cancel_by_customer(order, user, note=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in CUSTOMER_CANCELLABLE:
        raise Conflict("This order can no longer be cancelled. Please contact support.", code="not_cancellable")
    return change_status(order, S.CANCELLED, user=user, note=note or "Cancelled by the customer")


@transaction.atomic
def override_shipping(order, *, charge, reason, user):
    """
    Admin only (the view enforces it): set the shipping charge by hand, with a mandatory reason that
    goes into the order's history. Allowed until the order ships. Editing the order later re-resolves
    the charge from the zone and clears the override.
    """
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in OVERRIDABLE_SHIPPING:
        raise Conflict("The shipping charge can't be changed once the order has shipped or ended.", code="shipping_locked")
    reason = (reason or "").strip()
    if not reason:
        raise field_error("reason", "A reason is required.", "reason_required")
    charge = shipping_services.validate_charge(charge)
    old = order.shipping_charge
    order.shipping_charge = charge
    order.shipping_overridden = True
    order.shipping_override_reason = reason[:255]
    order.shipping_free_reason = ""
    _recalculate_total(order)
    order.save()
    OrderStatusHistory.objects.create(
        order=order, from_status=order.status, to_status=order.status, changed_by=user,
        note=f"Shipping charge overridden from {old} to {charge}: {reason}"[:500],
    )
    return order


def add_note(order, user, text):
    return OrderNote.objects.create(order=order, author=user, text=text)


@transaction.atomic
def delete_order(order):
    """Admin only. Soft delete, and only for orders that are already over (their stock and coupon are already released)."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in DELETABLE:
        raise Conflict("Only cancelled, failed or returned orders can be deleted. Cancel it first.", code="order_not_deletable")
    order.delete()


# --- lookups --------------------------------------------------------------------------------------------------------


def find_for_tracking(number, phone):
    """The order with this number and phone, or None. The caller must not say which of the two was wrong."""
    return Order.objects.filter(number=(number or "").strip().upper(), phone=phone).prefetch_related("items", "history").first()


def pickable_lines(search="", limit=20):
    """
    Rows for the order form's product picker: each buyable product, or each active variant of one that has
    variants, with just what a CCE needs to take an order (no cost or supplier data).
    """
    products = Product.objects.filter(status="published")
    term = (search or "").strip()
    if term:
        products = products.filter(Q(name__icontains=term) | Q(sku__icontains=term) | Q(variants__sku__icontains=term)).distinct()
    rows = []
    needle = term.lower()
    for product in products.order_by("name").prefetch_related("variants")[:limit]:
        if product.has_variants:
            # Typing one variant's SKU means that variant, not the whole product.
            matched_by_product = not needle or needle in product.name.lower() or needle in product.sku.lower()
            for variant in product.variants.all():
                if variant.is_active and (matched_by_product or needle in variant.sku.lower()):
                    rows.append((product, variant))
        else:
            rows.append((product, None))
    return [
        {
            "product_id": p.id, "variant_id": v.id if v else None, "slug": p.slug, "has_variants": p.has_variants,
            "name": p.name, "sku": v.sku if v else p.sku,
            "variant_label": _variant_label(v), "price": (v or p).effective_price,
            "stock": (v or p).stock_quantity if (v or p).manage_stock else None,
            "image": (v.image if v and v.image else p.feature_image),
        }
        for p, v in rows
    ]
