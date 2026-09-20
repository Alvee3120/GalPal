from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.catalog.models import Brand, Category, Product
from apps.core.models import TimeStampedModel
from apps.core.validators import validate_bd_phone

_min_zero = MinValueValidator(0)


class CouponType(models.TextChoices):
    FLAT = "flat", "Flat amount"
    PERCENTAGE = "percentage", "Percentage"


class Coupon(TimeStampedModel):
    """
    A discount code. `code` is always stored upper-cased (case-insensitive in practice) —
    normalized both here and in `serializers.validate_code`, since the serializer's own
    uniqueness check needs the canonical form *before* it runs, not after `save()`.

    Applicability (`products`/`categories`/`brands`) is a union, not an intersection: if any are
    set, a cart line qualifies by matching *any* of them. A chosen category covers its
    sub-categories too. Empty on all three means "applies to everything". See `services.eligible_subtotal` for exactly how a line is matched.

    `first_order_only` is stored and admin-editable now, but there is no Order model yet to check
    it against — enforcement is deferred to Module 10's checkout, which is the only place that can
    know a customer's order history. `services.evaluate()` documents this explicitly.
    """

    code = models.CharField(max_length=32, unique=True)
    description = models.CharField(max_length=255, blank=True)

    type = models.CharField(max_length=10, choices=CouponType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    max_discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[_min_zero],
        help_text="Percentage coupons only: caps the discount in currency, e.g. 20% off up to ৳500.",
    )
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[_min_zero])

    start_at = models.DateTimeField(null=True, blank=True, help_text="Blank: usable immediately.")
    expiry_at = models.DateTimeField(null=True, blank=True, help_text="Blank: never expires.")
    is_active = models.BooleanField(default=True, db_index=True)

    total_usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Blank: unlimited.")
    per_customer_usage_limit = models.PositiveIntegerField(null=True, blank=True, help_text="Blank: unlimited.")

    products = models.ManyToManyField(Product, blank=True, related_name="coupons")
    categories = models.ManyToManyField(Category, blank=True, related_name="coupons")
    brands = models.ManyToManyField(Brand, blank=True, related_name="coupons")
    exclude_sale_items = models.BooleanField(default=False)
    first_order_only = models.BooleanField(default=False)
    free_shipping = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(type=CouponType.FLAT) | (Q(type=CouponType.PERCENTAGE) & Q(amount__lte=100)),
                name="coupon_percentage_amount_max_100",
            ),
            models.CheckConstraint(
                condition=Q(expiry_at__isnull=True) | Q(start_at__isnull=True) | Q(expiry_at__gt=models.F("start_at")),
                name="coupon_expiry_after_start",
            ),
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class CouponUsage(TimeStampedModel):
    """
    One redemption of a coupon, created by `services.redeem_coupon` when an order is placed
    (Module 10). `order_reference` is a plain string, not a FK, since there is no Order model yet;
    Module 10 should pass its order number here.

    `phone` is always recorded (the number used at redemption, whether from the account or from
    guest checkout) so per-customer limits "per user, and per phone for guests" can be checked
    uniformly, and so the row stays meaningful if the account is later deleted. `user` is an
    optional convenience link, `SET_NULL`ed if the account goes away.
    """

    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="usages")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="coupon_usages"
    )
    phone = models.CharField(max_length=11, validators=[validate_bd_phone])
    order_reference = models.CharField(max_length=64, blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[_min_zero])

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["coupon", "user"]),
            models.Index(fields=["coupon", "phone"]),
        ]
        constraints = [
            # Guards against a Module 10 bug that redeems the same coupon twice for the same order.
            models.UniqueConstraint(
                fields=["coupon", "order_reference"], condition=~Q(order_reference=""), name="couponusage_unique_order"
            ),
        ]

    def __str__(self):
        return f"{self.coupon_id} used by {self.user_id or self.phone}"
