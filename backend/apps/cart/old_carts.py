"""
Old / abandoned carts: customers' carts holding an item for MORE than 6 hours (Admin + CCE monitoring only).

Nothing is stored or scheduled — "old" is derived on every request from the existing `CartItem.created_at` (set once,
when the product is first put in the cart; changing the quantity only touches `updated_at`, so an item's age never
resets). An item is old when `now - created_at > 6h`, i.e. `created_at < now - 6h` (exactly 6h is NOT old). Only
items still in a cart count: removing an item or checking out (which deletes the ordered lines) drops it at once.
Only customer-account carts are listed (a guest cart has no name or phone to follow up with). Read-only: carts are
never changed, cleared or notified from here.
"""

from datetime import timedelta

from django.db.models import Count, Max, Min, Q
from django.utils import timezone

from .models import Cart, CartItem

OLD_AFTER = timedelta(hours=6)

# Age filters on the cart's OLDEST item (how long the customer has kept something in the cart), as the oldest item's
# age band: "6_24" = over 6 hours, up to 24; "1_3" = over 1 day, up to 3; "3_plus" = over 3 days.
AGE_FILTERS = ("6_24", "1_3", "3_plus")


def cutoff(now=None):
    """Items added before this moment are old (strictly more than 6 hours ago)."""
    return (now or timezone.now()) - OLD_AFTER


def is_old(item, now=None):
    return item.created_at < cutoff(now)


def old_carts(*, now=None, search="", age=""):
    """
    Customer carts with at least one item older than 6 hours — one row per customer (a customer has one cart),
    oldest first. Annotated with `oldest_item_at`, `line_count`, `old_line_count` and `last_activity_at`.
    """
    now = now or timezone.now()
    limit = cutoff(now)
    # Annotate over ALL of a cart's items first, then keep carts whose oldest item is old — filtering on items before
    # annotating would make the counts and last activity see only the old items.
    carts = (
        Cart.objects.filter(user__isnull=False)
        .select_related("user")
        .annotate(
            oldest_item_at=Min("items__created_at"),
            line_count=Count("items", distinct=True),
            old_line_count=Count("items", filter=Q(items__created_at__lt=limit), distinct=True),
            last_activity_at=Max("items__updated_at"),
        )
        .filter(oldest_item_at__lt=limit)
    )
    term = (search or "").strip()
    if term:
        matching = CartItem.objects.filter(product__name__icontains=term).values("cart_id")
        carts = carts.filter(
            Q(user__full_name__icontains=term) | Q(user__phone__icontains=term) | Q(user__email__icontains=term)
            | Q(pk__in=matching)
        )
    hours = lambda n: now - timedelta(hours=n)  # noqa: E731 - the moment that was `n` hours ago
    if age == "6_24":
        carts = carts.filter(oldest_item_at__gte=hours(24))  # (and already older than 6h)
    elif age == "1_3":
        carts = carts.filter(oldest_item_at__lt=hours(24), oldest_item_at__gte=hours(72))
    elif age == "3_plus":
        carts = carts.filter(oldest_item_at__lt=hours(72))
    return carts.order_by("oldest_item_at", "pk")


def customers_with_old_carts(now=None):
    """The dashboard number: distinct customers (one cart each) with an item older than 6 hours."""
    return Cart.objects.filter(user__isnull=False, items__created_at__lt=cutoff(now)).values("user_id").distinct().count()
