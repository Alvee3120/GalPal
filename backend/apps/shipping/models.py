from decimal import Decimal

from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import SlugModel, TimeStampedModel

_min_zero = MinValueValidator(Decimal("0"))


class District(models.Model):
    """
    One of Bangladesh's 64 districts. A fixed reference list (seeded by a data migration), not
    something admins edit day to day: zones *point at* districts.

    `aliases` holds the other spellings people really type (Chittagong/Chattogram, Comilla/Cumilla,
    ...) so an address written either way still matches its zone.
    """

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    division = models.CharField(max_length=40, db_index=True)
    aliases = ArrayField(models.CharField(max_length=60), blank=True, default=list)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class DeliveryZone(TimeStampedModel, SlugModel):
    """
    A delivery-charge zone. `charge` is what the Admin edits; orders never read it back — checkout
    copies it into a snapshot on the order (Module 10), so changing it can't alter past orders.

    Which addresses belong to the zone is `coverage` (see `ZoneDistrict`). Exactly one zone is the
    `is_default` fallback for addresses that match nothing else; it must stay active, so there is
    always somewhere for an unmatched address to land.
    """

    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True, help_text="Shown to the Admin only, e.g. how the zone is matched.")

    charge = models.DecimalField(max_digits=10, decimal_places=2, validators=[_min_zero])

    estimated_days_min = models.PositiveSmallIntegerField(null=True, blank=True)
    estimated_days_max = models.PositiveSmallIntegerField(null=True, blank=True)
    estimated_days_label = models.CharField(
        max_length=50, blank=True, help_text='Overrides the generated text, e.g. "Same day" or "1-2 days".'
    )

    free_shipping_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[_min_zero],
        help_text="Blank: use the global threshold from Site Settings. 0: never free. Otherwise the subtotal that makes shipping free here.",
    )

    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_default = models.BooleanField(default=False, help_text="The fallback zone for addresses no other zone covers.")

    districts = models.ManyToManyField(District, through="ZoneDistrict", related_name="zones", blank=True)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="shipping_zone_name_ci_unique"),
            models.CheckConstraint(condition=Q(charge__gte=0), name="shipping_zone_charge_gte_0"),
            models.CheckConstraint(
                condition=Q(free_shipping_threshold__isnull=True) | Q(free_shipping_threshold__gte=0),
                name="shipping_zone_threshold_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(estimated_days_min__isnull=True) | Q(estimated_days_max__isnull=True)
                | Q(estimated_days_min__lte=models.F("estimated_days_max")),
                name="shipping_zone_days_min_lte_max",
            ),
            # At most one default zone, enforced by the database...
            models.UniqueConstraint(fields=["is_default"], condition=Q(is_default=True), name="shipping_one_default_zone"),
            # ...and a default zone can never be inactive (there must always be an active fallback).
            models.CheckConstraint(condition=Q(is_default=False) | Q(is_active=True), name="shipping_default_zone_active"),
        ]

    def __str__(self):
        return self.name

    @property
    def estimated_days(self):
        """Human text for the delivery estimate: the explicit label, else built from min/max."""
        return format_estimated_days(self.estimated_days_min, self.estimated_days_max, self.estimated_days_label)


def format_estimated_days(minimum, maximum, label=""):
    if label:
        return label
    if minimum is None and maximum is None:
        return ""
    if minimum is None or maximum is None or minimum == maximum:
        days = maximum if minimum is None else minimum
        return f"{days} day" if days == 1 else f"{days} days"
    return f"{minimum}-{maximum} days"


class ZoneDistrict(models.Model):
    """
    A zone covers a district, either wholly (`areas` empty) or only the listed areas/thanas of it,
    which is how a district can be split (e.g. Dhaka city vs the rest of Dhaka) without a new model.

    Matching prefers a row whose `areas` contains the address's area over a whole-district row.
    The database guarantees one whole-district owner per district; area overlaps are checked in
    `services.validate_coverage`.
    """

    zone = models.ForeignKey(DeliveryZone, on_delete=models.CASCADE, related_name="coverage")
    district = models.ForeignKey(District, on_delete=models.CASCADE, related_name="zone_links")
    areas = ArrayField(models.CharField(max_length=100), blank=True, default=list, help_text="Empty: the whole district.")

    class Meta:
        ordering = ["district__name"]
        constraints = [
            models.UniqueConstraint(fields=["zone", "district"], name="shipping_zone_district_unique"),
            models.UniqueConstraint(
                fields=["district"], condition=Q(areas=[]), name="shipping_one_whole_district_owner"
            ),
        ]

    def __str__(self):
        return f"{self.zone_id} -> {self.district_id}"


class DeliveryMethod(TimeStampedModel, SlugModel):
    """
    Optional service level (Standard, Express) whose `extra_charge` is added on top of the zone
    charge. Inactive by default: a method only exists for customers once the Admin turns it on.
    """

    name = models.CharField(max_length=60)
    description = models.CharField(max_length=255, blank=True)
    extra_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[_min_zero])
    estimated_days_label = models.CharField(
        max_length=50, blank=True, help_text='Overrides the zone estimate when this method is chosen, e.g. "Next day".'
    )
    is_active = models.BooleanField(default=False, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="shipping_method_name_ci_unique"),
            models.CheckConstraint(condition=Q(extra_charge__gte=0), name="shipping_method_extra_gte_0"),
        ]

    def __str__(self):
        return self.name


class ShippingChargeHistory(models.Model):
    """
    Append-only log of zone charge changes. The zone link is SET_NULL (with `zone_name` kept) so the
    trail outlives a deleted zone; `old_charge` is null on the row written when a zone is created.
    Module 18's audit log can read this table or be fed from `services.change_charge`.
    """

    zone = models.ForeignKey(DeliveryZone, null=True, on_delete=models.SET_NULL, related_name="charge_history")
    zone_name = models.CharField(max_length=80)
    old_charge = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    new_charge = models.DecimalField(max_digits=10, decimal_places=2)
    changed_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "shipping charge history"

    def __str__(self):
        return f"{self.zone_name}: {self.old_charge} -> {self.new_charge}"
