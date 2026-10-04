"""
Admin discount rules → the price a product or variant sells for right now. The backend is the only place this is worked
out: product cards, product details, search, cart, checkout and the order snapshot all read
`Product.effective_price` / `ProductVariant.effective_price`, which call `admin_price` below.

THE RULE (deterministic, never stacked):
1. Only discounts that are switched on and inside their start/end window right now count.
2. A product-specific discount beats a category discount. Within the same level, the one giving the lowest price wins
   (ties: the older discount).
3. A discount is worked out on the REGULAR price (of the product, or of the variant): percentage → price × (100 − v)%,
   rounded to the paisa; fixed → price − v. A fixed amount bigger than the price doesn't apply to that item.
4. The product's own sale price (Product.discount_price inside its sale window) still exists: the item sells for the
   LOWER of its own sale price and the admin discount price. One reduction only, never both.
5. Coupons are separate and come after, on the resulting price (apps.coupons).

Category discounts include sub-categories, exactly like the shop's category filter (catalog.filters_product).

The live rules are held in a small in-process index (product id → rules), rebuilt when any discount, product-category
link or category changes (a shared version number in the cache tells other workers) and at least every
INDEX_MAX_AGE_SECONDS; whether a rule is inside its window is always checked against the current time.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.db.models import Case, DecimalField, F, Q, Value, When
from django.db.models.functions import Coalesce, Least, Round
from django.utils import timezone

from .models import Discount, DiscountKind, DiscountStatus, DiscountTarget

logger = logging.getLogger(__name__)

CENT = Decimal("0.01")
MONEY = DecimalField(max_digits=12, decimal_places=2)
VERSION_KEY = "discounts:index-version"
INDEX_MAX_AGE_SECONDS = 60
VERSION_CHECK_SECONDS = 1


@dataclass(frozen=True)
class Rule:
    id: int
    name: str
    kind: str
    value: Decimal
    target_type: str
    starts_at: object
    ends_at: object
    product_ids: frozenset

    def is_live(self, now):
        return self.starts_at <= now < self.ends_at

    @property
    def priority(self):
        return 0 if self.target_type == DiscountTarget.PRODUCTS else 1

    def price_for(self, base):
        """The discounted price of `base`, or None when this rule can't apply (fixed amount above the price)."""
        if base is None or base <= 0:
            return None
        if self.kind == DiscountKind.PERCENTAGE:
            price = (base * (Decimal(100) - self.value) / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)
        else:
            price = base - self.value
        return price if Decimal(0) <= price < base else None

    def as_dict(self):
        return {"id": self.id, "name": self.name, "type": self.kind, "value": self.value}


# --- the index ---------------------------------------------------------------------------------------------------------

_lock = threading.Lock()
_snapshot = None  # (version, built_at, checked_at, rules, by_product)


def _shared_version():
    try:
        return cache.get(VERSION_KEY)
    except Exception:  # noqa: BLE001 - cache down: fall back to the age limit
        return None


def invalidate():
    """Drop the index here and tell the other workers (call after any change to discounts or category links)."""
    global _snapshot
    with _lock:
        _snapshot = None
    try:
        cache.set(VERSION_KEY, uuid.uuid4().hex, None)
    except Exception:  # noqa: BLE001
        logger.warning("Could not publish the discount index version", exc_info=True)


def category_product_ids(category_ids):
    """Every product linked to any of these categories or a category below them (the shop's category-filter rule)."""
    from apps.catalog import services as catalog_services
    from apps.catalog.models import ProductCategory

    category_ids = {int(c) for c in category_ids or () if c}
    if not category_ids:
        return set()
    parents = catalog_services.parent_map()
    ids = set(category_ids)
    for category_id in category_ids:
        ids |= catalog_services.descendant_ids(category_id, parents)
    return set(ProductCategory.objects.filter(category_id__in=ids).values_list("product_id", flat=True))


def target_product_ids(discount):
    """Product ids a discount covers now: its chosen products, or the products of its categories."""
    if discount.target_type == DiscountTarget.PRODUCTS:
        return set(discount.products.values_list("id", flat=True))
    return category_product_ids(discount.categories.values_list("id", flat=True))


def _build():
    """
    Load the not-yet-expired, switched-on discounts. If they can't be read (e.g. the migration isn't applied yet) prices
    simply fall back to no Admin discounts — inside a savepoint, so a failed read never breaks the caller's transaction.
    """
    try:
        with transaction.atomic():
            return _load()
    except DatabaseError:
        logger.warning("Admin discounts unavailable; pricing without them", exc_info=True)
        return [], {}


def _load():
    now = timezone.now()
    rules, by_product = [], {}
    for discount in Discount.objects.filter(is_active=True, ends_at__gt=now).order_by("id"):
        rule = Rule(
            id=discount.id, name=discount.name, kind=discount.kind, value=discount.value, target_type=discount.target_type,
            starts_at=discount.starts_at, ends_at=discount.ends_at, product_ids=frozenset(target_product_ids(discount)),
        )
        rules.append(rule)
        for product_id in rule.product_ids:
            by_product.setdefault(product_id, []).append(rule)
    return rules, by_product


def _index():
    global _snapshot
    now = time.monotonic()
    snap = _snapshot
    if snap is not None and now - snap[2] < VERSION_CHECK_SECONDS:
        return snap[3], snap[4]
    version = _shared_version()
    if snap is not None and snap[0] == version and now - snap[1] < INDEX_MAX_AGE_SECONDS:
        with _lock:
            _snapshot = (snap[0], snap[1], now, snap[3], snap[4])
        return snap[3], snap[4]
    rules, by_product = _build()
    with _lock:
        _snapshot = (version, now, now, rules, by_product)
    return rules, by_product


def live_rules(now=None):
    now = now or timezone.now()
    return [rule for rule in _index()[0] if rule.is_live(now)]


# --- prices -----------------------------------------------------------------------------------------------------------


def admin_price(product_id, base_price, now=None):
    """(price, Rule) of the best live admin discount for this product at `base_price`, or (None, None)."""
    rules = _index()[1].get(product_id)
    if not rules:
        return None, None
    now = now or timezone.now()
    best = None
    for rule in rules:
        if not rule.is_live(now):
            continue
        price = rule.price_for(base_price)
        if price is None:
            continue
        key = (rule.priority, price, rule.id)
        if best is None or key < best[0]:
            best = (key, price, rule)
    return (best[1], best[2]) if best else (None, None)


def resolve(product_id, regular_price, own_sale_price):
    """
    (effective price, applied Rule or None) — the single reduction an item gets: the lower of its own sale price
    (already None when the sale window is closed) and the best admin discount; never both.
    """
    discounted, rule = admin_price(product_id, regular_price)
    if discounted is not None and (own_sale_price is None or discounted < own_sale_price):
        return discounted, rule
    if own_sale_price is not None:
        return own_sale_price, None
    return regular_price, None


def priced_product_ids(rule):
    """
    Published products this live rule is pricing right now — the ones whose single effective reduction (`resolve`) IS
    this discount. A product it covers but that sells cheaper through a product-specific discount or its own sale price
    is left out, so a homepage section never shows a price that came from somewhere else.
    """
    from apps.catalog.models import Product, ProductStatus

    ids = []
    for p in Product.objects.filter(pk__in=rule.product_ids, status=ProductStatus.PUBLISHED).only(
        "id", "regular_price", "discount_price", "sale_start_at", "sale_end_at"
    ):
        own = p.discount_price if p.own_sale_active else None
        price, applied = resolve(p.pk, p.regular_price, own)
        if applied is not None and applied.id == rule.id and price < p.regular_price:
            ids.append(p.pk)
    return ids


def storefront_discounts(now=None):
    """
    Live discounts for the storefront (homepage sections), each with the ids of the products it is pricing; discounts
    that price nothing right now are left out. Newest start first, like the admin list.
    """
    now = now or timezone.now()
    shown = []
    for rule in sorted(live_rules(now), key=lambda r: (r.starts_at, r.id), reverse=True):
        ids = priced_product_ids(rule)
        if ids:
            shown.append((rule, ids))
    return shown


def live_rule(discount_id, now=None):
    return next((r for r in live_rules(now) if r.id == discount_id), None)


def annotate_admin_price(queryset, now=None):
    """
    `admin_price_db`: the same rule as `admin_price`, as SQL on the product's regular price (NULL when no live discount
    applies), for price sorting, price-range and on-sale filters. Product-level only, like the existing sale price.
    """
    rules = live_rules(now)
    if not rules:
        return queryset.annotate(admin_price_db=Value(None, output_field=MONEY))

    def expression(rule):
        if not rule.product_ids:
            return None
        base = F("regular_price")
        if rule.kind == DiscountKind.PERCENTAGE:
            price = Round(base * Value((Decimal(100) - rule.value) / Decimal(100)), 2, output_field=MONEY)
            condition = Q(pk__in=rule.product_ids)
        else:
            price = base - Value(rule.value, output_field=MONEY)
            condition = Q(pk__in=rule.product_ids, regular_price__gte=rule.value)
        return Case(When(condition, then=price), default=Value(None, output_field=MONEY), output_field=MONEY)

    def lowest(exprs):
        exprs = [e for e in exprs if e is not None]
        if not exprs:
            return None
        return exprs[0] if len(exprs) == 1 else Least(*exprs, output_field=MONEY)  # PostgreSQL LEAST skips NULLs

    product_level = lowest(expression(r) for r in rules if r.target_type == DiscountTarget.PRODUCTS)
    category_level = lowest(expression(r) for r in rules if r.target_type == DiscountTarget.CATEGORY)
    tiers = [t for t in (product_level, category_level) if t is not None]
    if not tiers:
        return queryset.annotate(admin_price_db=Value(None, output_field=MONEY))
    combined = tiers[0] if len(tiers) == 1 else Coalesce(*tiers, output_field=MONEY)  # product-specific wins
    return queryset.annotate(admin_price_db=combined)


# --- status & validation ------------------------------------------------------------------------------------------------


def status_of(discount, now=None):
    now = now or timezone.now()
    if not discount.is_active:
        return DiscountStatus.INACTIVE
    if now < discount.starts_at:
        return DiscountStatus.SCHEDULED
    if now >= discount.ends_at:
        return DiscountStatus.EXPIRED
    return DiscountStatus.ACTIVE


def status_q(status, now=None):
    """The same status as a filter."""
    now = now or timezone.now()
    return {
        DiscountStatus.INACTIVE: Q(is_active=False),
        DiscountStatus.SCHEDULED: Q(is_active=True, starts_at__gt=now),
        DiscountStatus.EXPIRED: Q(is_active=True, ends_at__lte=now),
        DiscountStatus.ACTIVE: Q(is_active=True, starts_at__lte=now, ends_at__gt=now),
    }[status]


def items_priced_below(product_ids, amount, limit=5):
    """Names of products / active variants (among `product_ids`) whose regular price is below a fixed `amount`."""
    from apps.catalog.models import Product, ProductVariant

    names = list(Product.objects.filter(pk__in=product_ids, regular_price__lt=amount).values_list("name", flat=True)[:limit])
    variants = (
        ProductVariant.objects.filter(product_id__in=product_ids, is_active=True, regular_price__lt=amount)
        .select_related("product")[:limit]
    )
    names += [f"{v.product.name} ({v.sku})" for v in variants]
    return names[:limit]
