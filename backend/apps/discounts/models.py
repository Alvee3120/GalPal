"""
Admin discounts.

Two families share this one model so Admin manages them in a single place:

* **Product price discounts** (`percentage`, `fixed`) — automatic, time-boxed price reductions on one or more categories
  (with their sub-categories) or on chosen products. They never write a price anywhere: `Product.effective_price`
  (apps.catalog.models) asks `apps.discounts.services` for the best live discount and compares it with the product's own
  sale price, so the regular price is always intact and everything returns to normal the moment a discount ends or is
  switched off.

* **Cart promotions** (`buy_x_get_y_percent`, `buy_x_get_y_free`, `lowest_free`, `three_for_two`, `bundle_price`) — offers
  that depend on how many eligible units are in the cart, not on a single product's price, so they are worked out over
  the whole cart/order by `apps.discounts.promotions` (cart display, checkout, order snapshot and invoice all use the
  same engine). They never touch `effective_price`.

Coupons (apps.coupons) are a separate thing: codes a customer types at checkout, applied on top of the current price.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel


class DiscountKind(models.TextChoices):
    # Product price discounts (change `effective_price`).
    PERCENTAGE = "percentage", "Percentage"
    FIXED = "fixed", "Fixed amount"
    # Cart promotions (evaluated over the cart by apps.discounts.promotions).
    BUY_X_GET_Y_PERCENT = "buy_x_get_y_percent", "Buy X items, get Y% off"
    BUY_X_GET_Y_FREE = "buy_x_get_y_free", "Buy X, get Y free"
    LOWEST_FREE = "lowest_free", "Buy X, get the lowest-priced item free"
    THREE_FOR_TWO = "three_for_two", "3 for 2"
    BUNDLE_PRICE = "bundle_price", "Buy X products for a fixed price"


# Product kinds modify a single product's price; cart kinds are quantities-of-the-cart offers. Only product kinds may
# ever reach `effective_price` — see apps.discounts.services.admin_price.
PRODUCT_KINDS = frozenset({DiscountKind.PERCENTAGE, DiscountKind.FIXED})
CART_KINDS = frozenset(
    {
        DiscountKind.BUY_X_GET_Y_PERCENT,
        DiscountKind.BUY_X_GET_Y_FREE,
        DiscountKind.LOWEST_FREE,
        DiscountKind.THREE_FOR_TWO,
        DiscountKind.BUNDLE_PRICE,
    }
)


class DiscountTarget(models.TextChoices):
    CATEGORY = "category", "Category"
    PRODUCTS = "products", "Specific products"


class DiscountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SCHEDULED = "scheduled", "Scheduled"
    EXPIRED = "expired", "Expired"
    INACTIVE = "inactive", "Inactive"


def _num(value):
    """A Decimal as a plain string without trailing zeros ("20.00" -> "20", "1000.00" -> "1000")."""
    if value is None:
        return ""
    return format(Decimal(value).normalize(), "f")


def promotion_label(discount, symbol="৳"):
    """Customer-facing one-liner for a discount, e.g. "Buy 3, get 20% off" or "3 products for ৳1000"."""
    kind = discount.kind
    if kind == DiscountKind.PERCENTAGE:
        return f"{_num(discount.value)}% off"
    if kind == DiscountKind.FIXED:
        return f"{symbol}{_num(discount.value)} off"
    if kind == DiscountKind.BUY_X_GET_Y_PERCENT:
        return f"Buy {discount.min_quantity}, get {_num(discount.percent_off)}% off"
    if kind == DiscountKind.BUY_X_GET_Y_FREE:
        return f"Buy {discount.min_quantity}, get {discount.free_quantity} free"
    if kind == DiscountKind.LOWEST_FREE:
        return f"Buy {discount.min_quantity}, lowest-priced item free"
    if kind == DiscountKind.THREE_FOR_TWO:
        return "3 for 2"
    if kind == DiscountKind.BUNDLE_PRICE:
        return f"{discount.min_quantity} products for {symbol}{_num(discount.bundle_price)}"
    return ""


class Discount(TimeStampedModel):
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=24, choices=DiscountKind.choices)
    value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Percent (0–100] or taka off, depending on `kind`. Only used by the percentage / fixed product kinds.",
    )
    target_type = models.CharField(max_length=10, choices=DiscountTarget.choices)
    categories = models.ManyToManyField("catalog.Category", blank=True, related_name="discounts",
                                        help_text="Category target: these categories and every sub-category below them.")
    products = models.ManyToManyField("catalog.Product", blank=True, related_name="discounts")

    # Cart-promotion configuration (null / default for the product kinds).
    min_quantity = models.PositiveIntegerField(
        null=True, blank=True, help_text="X: how many eligible units are needed to form one offer group.")
    percent_off = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, help_text="Y% off, for 'Buy X items, get Y% off'.")
    free_quantity = models.PositiveIntegerField(null=True, blank=True, help_text="Y, for 'Buy X, get Y free'.")
    bundle_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="৳Y: the total payable price of one group of X eligible products.")
    same_product_group = models.BooleanField(
        default=False, help_text="Free units must come from the same eligible product (variant) as the paid ones.")
    allow_repeat = models.BooleanField(
        default=True, help_text="Apply the offer once per complete group (off = only the first group counts).")
    priority = models.PositiveIntegerField(
        default=100, help_text="Lower runs first when two cart promotions compete for the same units.")

    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True, db_index=True, help_text="Off = never applies, whatever the dates.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-starts_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="discount_ends_after_start"),
            # value only matters for the product percentage / fixed kinds
            models.CheckConstraint(
                condition=~Q(kind__in=["percentage", "fixed"]) | Q(value__gt=0), name="discount_value_positive"
            ),
            models.CheckConstraint(condition=~Q(kind="percentage") | Q(value__lte=100), name="discount_percentage_lte_100"),
            models.CheckConstraint(
                condition=~Q(kind="buy_x_get_y_percent") | (Q(percent_off__gt=0) & Q(percent_off__lte=100)),
                name="discount_percent_off_range",
            ),
            models.CheckConstraint(
                condition=~Q(kind__in=["buy_x_get_y_percent", "buy_x_get_y_free", "lowest_free", "bundle_price"])
                | Q(min_quantity__gte=1),
                name="discount_min_quantity_positive",
            ),
            models.CheckConstraint(
                condition=~Q(kind="buy_x_get_y_free") | Q(free_quantity__gte=1), name="discount_free_quantity_positive"
            ),
            models.CheckConstraint(
                condition=~Q(kind="bundle_price") | Q(bundle_price__gt=0), name="discount_bundle_price_positive"
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_cart_promotion(self):
        return self.kind in CART_KINDS

    @property
    def label(self):
        """Customer-facing one-liner for this discount (see `promotion_label`)."""
        return promotion_label(self)
