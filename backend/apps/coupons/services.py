"""
Coupon business logic: checking whether a coupon can be used, computing its discount for a cart,
applying/removing it, and the final, row-locked redemption Module 10 will call at checkout.

Two distinct checks, deliberately kept separate:
  * `evaluate()` — read-only, used both when applying a coupon and when displaying a cart. Never
    raises; it reports whether the coupon currently works and why not.
  * `redeem_coupon()` — the one-time, authoritative check + usage record at order placement,
    under a row lock so two concurrent orders can't both claim the last use of a limited coupon.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.catalog import services as catalog_services

from .exceptions import field_error
from .models import Coupon, CouponType, CouponUsage

CENTS = Decimal("0.01")


def _is_within_schedule(coupon, now=None):
    now = now or timezone.now()
    if coupon.start_at and now < coupon.start_at:
        return False
    if coupon.expiry_at and now > coupon.expiry_at:
        return False
    return True


def total_usage_count(coupon):
    return CouponUsage.objects.filter(coupon=coupon).count()


def usage_count(coupon, *, user=None, phone=None):
    if user is not None and user.is_authenticated:
        return CouponUsage.objects.filter(coupon=coupon, user=user).count()
    if phone:
        return CouponUsage.objects.filter(coupon=coupon, phone=phone).count()
    return 0


def _line_qualifies(coupon, product, restricted, product_ids, category_ids, brand_ids):
    if coupon.exclude_sale_items and product.on_sale:
        return False
    if not restricted:
        return True
    category_matches = set(product.category_links.values_list("category_id", flat=True)) & category_ids
    return product.id in product_ids or product.brand_id in brand_ids or bool(category_matches)


def eligible_subtotal(coupon, rows):
    """Sum of available cart lines this coupon's discount applies to (see `Coupon` for the rule)."""
    product_ids = set(coupon.products.values_list("id", flat=True))
    category_ids = set(coupon.categories.values_list("id", flat=True))
    if category_ids:
        # Choosing "Skincare" means everything under it too (as the public category filter does).
        parents = catalog_services.parent_map()
        for category_id in list(category_ids):
            category_ids |= catalog_services.descendant_ids(category_id, parents)
    brand_ids = set(coupon.brands.values_list("id", flat=True))
    restricted = bool(product_ids or category_ids or brand_ids)  # (after expansion: same truthiness)

    total = Decimal("0.00")
    for row in rows:
        if not row["is_available"]:
            continue
        if _line_qualifies(coupon, row["item"].product, restricted, product_ids, category_ids, brand_ids):
            total += row["line_total"]
    return total


def compute_discount(coupon, rows):
    """The discount this coupon gives on `rows` right now — never more than the eligible subtotal."""
    base = eligible_subtotal(coupon, rows)
    if base <= 0:
        return Decimal("0.00")
    if coupon.type == CouponType.FLAT:
        discount = coupon.amount
    else:
        discount = (base * coupon.amount / Decimal("100")).quantize(CENTS, rounding=ROUND_HALF_UP)
        if coupon.max_discount_amount is not None:
            discount = min(discount, coupon.max_discount_amount)
    return min(discount, base)


def evaluate(coupon, *, subtotal, rows, user=None, phone=None):
    """
    `(is_valid, message, discount)` for `coupon` against a cart's current `subtotal`/`rows`.

    Never raises. `first_order_only` is intentionally not checked here — there is no Order model
    yet to check it against (see the `Coupon.first_order_only` docstring); Module 10's checkout is
    where that must finally be enforced, in addition to everything checked here.
    """
    if not coupon.is_active:
        return False, "This coupon is not active.", Decimal("0.00")
    if not _is_within_schedule(coupon):
        return False, "This coupon is not currently valid.", Decimal("0.00")
    if subtotal < coupon.min_order_amount:
        return False, f"Minimum order amount is {coupon.min_order_amount}.", Decimal("0.00")
    if coupon.total_usage_limit is not None and total_usage_count(coupon) >= coupon.total_usage_limit:
        return False, "This coupon has reached its usage limit.", Decimal("0.00")
    if coupon.per_customer_usage_limit is not None:
        if usage_count(coupon, user=user, phone=phone) >= coupon.per_customer_usage_limit:
            return False, "You have already used this coupon the maximum number of times.", Decimal("0.00")
    discount = compute_discount(coupon, rows)
    if discount <= 0:
        return False, "This coupon does not apply to anything in your cart.", Decimal("0.00")
    return True, "", discount


@transaction.atomic
def apply_coupon_to_cart(cart, code, *, user=None, phone=None):
    """Validate `code` against the cart's current contents and attach it. Raises on any failure."""
    coupon = Coupon.objects.filter(code=(code or "").strip().upper()).first()
    if coupon is None:
        raise field_error("code", "Invalid coupon code.", "not_found")

    from apps.cart import services as cart_services  # lazy: avoids a cart <-> coupons import cycle

    summary = cart_services.summarize(cart)
    is_valid, message, _ = evaluate(coupon, subtotal=summary["subtotal"], rows=summary["rows"], user=user, phone=phone)
    if not is_valid:
        raise field_error("code", message, "coupon_not_applicable")

    cart.coupon = coupon
    cart.save(update_fields=["coupon", "updated_at"])
    return coupon


def remove_coupon_from_cart(cart):
    if cart.coupon_id is not None:
        cart.coupon = None
        cart.save(update_fields=["coupon", "updated_at"])


@transaction.atomic
def redeem_coupon(coupon, *, phone, order_reference, discount_amount, user=None):
    """
    The authoritative, one-time check + usage record for Module 10's checkout to call when an
    order is actually placed. Locks the coupon row so two concurrent orders can't both slip past
    a usage limit that only one of them should be allowed to reach.
    """
    discount_amount = Decimal(str(discount_amount))
    locked = Coupon.objects.select_for_update().get(pk=coupon.pk)
    if not locked.is_active or not _is_within_schedule(locked):
        raise field_error("coupon", "This coupon is no longer valid.", "coupon_invalid")
    if locked.total_usage_limit is not None and total_usage_count(locked) >= locked.total_usage_limit:
        raise field_error("coupon", "This coupon has reached its usage limit.", "usage_limit_reached")
    if locked.per_customer_usage_limit is not None:
        if usage_count(locked, user=user, phone=phone) >= locked.per_customer_usage_limit:
            raise field_error("coupon", "This coupon has already been used the maximum number of times.", "per_customer_limit_reached")
    return CouponUsage.objects.create(
        coupon=locked, user=user, phone=phone, order_reference=order_reference, discount_amount=discount_amount
    )
