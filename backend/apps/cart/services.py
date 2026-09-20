"""
Cart business logic: resolving whose cart a request means, adding/updating/removing items with
live stock and price checks, merging a guest cart into a user's on login, and summarizing totals.

A cart is never looked up with the ORM directly outside this module — always go through
`get_cart`, so the "logged-in user XOR guest token" rule and the merge-on-login behaviour stay
in one place.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalog.models import Product, ProductStatus, ProductVariant, StockStatus

from .exceptions import field_error
from .models import Cart, CartItem

CART_TOKEN_HEADER = "X-Cart-Token"


def token_from_request(request):
    """Read & parse the guest cart token from the X-Cart-Token header, or None if absent/invalid."""
    raw = request.headers.get(CART_TOKEN_HEADER)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError):
        return None


def get_cart(request, *, create=False):
    """
    The cart for this request: the logged-in user's cart, or the guest cart named by the
    `X-Cart-Token` header. Returns `None` for a guest with no (valid) token unless `create=True`,
    in which case a fresh guest cart is made and its token must be sent back to the client
    (`views` does this via the response body and the same header).
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    token = token_from_request(request)
    if token is not None:
        cart = Cart.objects.filter(token=token).first()
        if cart is not None:
            return cart

    if not create:
        return None
    return Cart.objects.create(token=Cart.new_token())


def _assert_addable(product, variant):
    if product.status != ProductStatus.PUBLISHED or product.is_deleted:
        raise field_error("product_id", "This product is not available.", "product_unavailable")
    if product.has_variants:
        if variant is None:
            raise field_error("variant_id", "Choose a variant of this product.", "variant_required")
        if variant.product_id != product.pk:
            raise field_error("variant_id", "This variant does not belong to this product.", "variant_mismatch")
        if not variant.is_active:
            raise field_error("variant_id", "This variant is not available.", "variant_unavailable")
    elif variant is not None:
        raise field_error("variant_id", "This product does not have variants.", "variant_not_allowed")


def available_quantity(target):
    """
    Units of `target` (a Product or ProductVariant) that can be added, or `None` if uncapped
    (stock isn't managed, or it's on backorder — matching `Product.in_stock`'s own rule).

    `stock_status` (and so "backorder") only exists on `Product`; a variant defers to its own
    product for it, since a variant has no backorder concept of its own.
    """
    if not target.manage_stock:
        return None
    product = target if isinstance(target, Product) else target.product
    if product.stock_status == StockStatus.BACKORDER:
        return None
    return target.stock_quantity


@transaction.atomic
def add_item(cart, *, product_id, variant_id=None, quantity):
    """
    Add `quantity` of a product (or variant) to the cart, or increase an existing line by that
    amount ("Add to cart" semantics — use `set_item_quantity` for "set the quantity to N").
    """
    try:
        product = Product.objects.select_for_update().get(pk=product_id)
    except Product.DoesNotExist:
        raise field_error("product_id", "Product not found.", "not_found") from None

    variant = None
    if variant_id is not None:
        variant = ProductVariant.objects.select_for_update().filter(pk=variant_id).first()
        if variant is None:
            raise field_error("variant_id", "Variant not found.", "not_found")

    _assert_addable(product, variant)

    item = CartItem.objects.select_for_update().filter(cart=cart, product=product, variant=variant).first()
    new_quantity = (item.quantity if item else 0) + quantity
    _assert_quantity_available(variant or product, new_quantity)
    if item is None:
        item = CartItem(cart=cart, product=product, variant=variant)
    item.quantity = new_quantity
    item.full_clean()
    item.save()
    return item


@transaction.atomic
def set_item_quantity(item, quantity):
    """Set a line's quantity to an absolute value (the cart page's quantity stepper)."""
    target = ProductVariant.objects.select_for_update().get(pk=item.variant_id) if item.variant_id else (
        Product.objects.select_for_update().get(pk=item.product_id)
    )
    _assert_quantity_available(target, quantity)
    item.quantity = quantity
    item.full_clean()
    item.save(update_fields=["quantity", "updated_at"])
    return item


def _assert_quantity_available(target, quantity):
    cap = available_quantity(target)
    if cap is not None and quantity > cap:
        raise field_error(
            "quantity", f"Only {cap} left in stock." if cap else "Out of stock.", "insufficient_stock"
        )


def remove_item(item):
    item.delete()


@transaction.atomic
def merge_guest_cart_into_user(token, user):
    """
    Fold the guest cart named by `token` into `user`'s cart (creating it if needed) and delete the
    guest cart. Called right after login/registration. Quantities of a line already in both carts
    are added together, capped at whatever stock still allows. Never raises: a merge problem
    should not block login, so any single line that no longer fits is silently capped or dropped.
    """
    if token is None:
        return
    guest_cart = Cart.objects.filter(token=token).select_for_update().first()
    if guest_cart is None:
        return

    user_cart, _ = Cart.objects.get_or_create(user=user)
    # No select_related("variant") here: it's a nullable FK, so Postgres refuses FOR UPDATE on
    # the resulting outer join. `variant` is fetched lazily per item instead (a handful at most).
    for guest_item in guest_cart.items.select_related("product").select_for_update():
        target = guest_item.variant or guest_item.product
        existing = CartItem.objects.filter(cart=user_cart, product=guest_item.product, variant=guest_item.variant).first()
        combined = (existing.quantity if existing else 0) + guest_item.quantity
        cap = available_quantity(target)
        if cap is not None:
            combined = min(combined, cap)
        if combined <= 0:
            continue
        if existing:
            existing.quantity = combined
            existing.save(update_fields=["quantity", "updated_at"])
        else:
            CartItem.objects.create(cart=user_cart, product=guest_item.product, variant=guest_item.variant, quantity=combined)
    # Keep a coupon the guest applied, unless the account's cart already has its own. No need to
    # re-validate: `summarize` re-evaluates it live on every read anyway.
    if guest_cart.coupon_id is not None and user_cart.coupon_id is None:
        user_cart.coupon_id = guest_cart.coupon_id
        user_cart.save(update_fields=["coupon", "updated_at"])
    guest_cart.delete()
    return user_cart


# --- summary -----------------------------------------------------------------------------------


def line_price(item):
    """(unit_price, is_available, available_qty) for one cart line, computed live."""
    target = item.variant if item.variant_id else item.product
    try:
        _assert_addable(item.product, item.variant)
        available = True
    except ValidationError:
        available = False
    cap = available_quantity(target)
    if available and cap is not None and cap < item.quantity:
        available = False
    return target.effective_price, available, cap


def summarize(cart):
    """
    `{items, item_count, subtotal, discount, coupon, shipping, total}` for a cart (or `None` for
    an empty/nonexistent guest cart). Unavailable lines (out of stock, deactivated, discontinued)
    are still listed, so the frontend can show them, but excluded from every total.

    `discount` comes from the cart's applied coupon (Module 8), recomputed live like everything
    else here — a coupon that's stopped applying (cart no longer meets its minimum, e.g.) reports
    `discount=0` and `coupon.is_valid=False` without being detached, so it resumes automatically
    if the cart changes again. `shipping` is a placeholder shape (`{"amount": null, "note": "..."}`)
    until Module 9 (delivery zones) can compute a real one, except that a free-shipping coupon
    already zeroes it out.
    """
    items = list(cart.items.select_related("product", "variant__product")) if cart else []
    subtotal = Decimal("0.00")
    rows = []
    for item in items:
        unit_price, is_available, cap = line_price(item)
        line_total = unit_price * item.quantity if is_available else Decimal("0.00")
        if is_available:
            subtotal += line_total
        rows.append({"item": item, "unit_price": unit_price, "line_total": line_total, "is_available": is_available, "available_quantity": cap})

    discount = Decimal("0.00")
    coupon_summary = None
    shipping = {"amount": None, "note": "Calculated at checkout"}
    if cart is not None and cart.coupon_id is not None:
        from apps.coupons import services as coupon_services  # lazy: avoids a cart <-> coupons import cycle

        is_valid, message, discount = coupon_services.evaluate(cart.coupon, subtotal=subtotal, rows=rows, user=cart.user)
        coupon_summary = {"code": cart.coupon.code, "is_valid": is_valid, "message": message}
        if is_valid and cart.coupon.free_shipping:
            shipping = {"amount": Decimal("0.00"), "note": "Free shipping (coupon applied)"}

    return {
        "rows": rows,
        "item_count": sum(item.quantity for item in items),
        "subtotal": subtotal,
        "discount": discount,
        "coupon": coupon_summary,
        "shipping": shipping,
        "total": subtotal - discount,
    }
