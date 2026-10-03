"""
Admin discounts: automatic, time-boxed price reductions on one or more categories (with their sub-categories) or on
chosen products.

A discount never writes a price anywhere. Product / variant `effective_price` (apps.catalog.models) asks
`apps.discounts.services` for the best live discount and compares it with the product's own sale price, so the regular
price is always intact and everything returns to normal the moment a discount ends or is switched off. Coupons
(apps.coupons) are a separate thing: codes a customer types at checkout, applied on top of the current price.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel


class DiscountKind(models.TextChoices):
    PERCENTAGE = "percentage", "Percentage"
    FIXED = "fixed", "Fixed amount"


class DiscountTarget(models.TextChoices):
    CATEGORY = "category", "Category"
    PRODUCTS = "products", "Specific products"


class DiscountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SCHEDULED = "scheduled", "Scheduled"
    EXPIRED = "expired", "Expired"
    INACTIVE = "inactive", "Inactive"


class Discount(TimeStampedModel):
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=DiscountKind.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
                                help_text="Percent (0–100] or taka off, depending on `kind`.")
    target_type = models.CharField(max_length=10, choices=DiscountTarget.choices)
    categories = models.ManyToManyField("catalog.Category", blank=True, related_name="discounts",
                                        help_text="Category target: these categories and every sub-category below them.")
    products = models.ManyToManyField("catalog.Product", blank=True, related_name="discounts")
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True, db_index=True, help_text="Off = never applies, whatever the dates.")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-starts_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="discount_ends_after_start"),
            models.CheckConstraint(condition=Q(value__gt=0), name="discount_value_positive"),
            models.CheckConstraint(condition=~Q(kind="percentage") | Q(value__lte=100), name="discount_percentage_lte_100"),
        ]

    def __str__(self):
        return self.name
