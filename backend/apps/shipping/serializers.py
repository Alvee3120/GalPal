from decimal import Decimal

from rest_framework import serializers

from apps.core.serializers import SlugSerializerMixin

from . import services
from .models import DeliveryMethod, DeliveryZone, District, ShippingChargeHistory


def _charge(value):
    try:
        return services.check_charge(value)
    except services.InvalidCharge as exc:
        raise serializers.ValidationError(exc.message, code=exc.code) from None


# --- public -------------------------------------------------------------------------------------------


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ["id", "name", "slug", "division"]


class PublicZoneSerializer(serializers.Serializer):
    """Built from the cached zone snapshot (a dict), not a model instance."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    charge = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimated_days = serializers.CharField(allow_blank=True)
    free_shipping_threshold = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True,
        help_text="Subtotal at which shipping is free in this zone (its own override, else the global one); null: never free.",
    )
    is_default = serializers.BooleanField(help_text="The fallback zone: every district not listed elsewhere.")
    districts = serializers.ListField(child=serializers.CharField(), help_text="Districts this zone names (the default zone covers the rest).")
    areas = serializers.ListField(
        source="area_names", child=serializers.DictField(), default=list,
        help_text='Area-limited coverage, e.g. [{"district": "Dhaka", "areas": ["Savar", ...]}] — the storefront lists these as zones.',
    )


class PublicMethodSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    extra_charge = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimated_days = serializers.CharField(allow_blank=True)


class CalculateShippingSerializer(serializers.Serializer):
    district = serializers.CharField(max_length=100)
    area = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False,
        help_text="The cart subtotal. Omit it to use the current cart (guest header token or login).",
    )
    delivery_method = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")


class _QuoteMethodSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()
    extra_charge = serializers.DecimalField(max_digits=10, decimal_places=2)


class ShippingQuoteSerializer(serializers.Serializer):
    zone_id = serializers.IntegerField()
    zone_name = serializers.CharField()
    charge = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="What the customer pays (0 when free).")
    is_free = serializers.BooleanField()
    free_shipping_reason = serializers.CharField(allow_null=True, help_text="`free_shipping_threshold`, `coupon_free_shipping` or null.")
    estimated_days = serializers.CharField(allow_blank=True)
    zone_charge = serializers.DecimalField(max_digits=10, decimal_places=2, help_text="The zone's own charge before any free-shipping rule.")
    delivery_method = _QuoteMethodSerializer(allow_null=True)
    free_shipping_threshold = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)


# --- admin: zones -------------------------------------------------------------------------------------


class CoverageItemSerializer(serializers.Serializer):
    district_id = serializers.IntegerField(min_value=1)
    areas = serializers.ListField(
        child=serializers.CharField(max_length=100), required=False, default=list,
        help_text="Areas/thanas of the district this zone covers. Empty: the whole district.",
    )
    district_name = serializers.CharField(read_only=True, source="district.name")


class AdminZoneSerializer(SlugSerializerMixin, serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True, max_length=255)
    coverage = CoverageItemSerializer(many=True, required=False)
    estimated_days = serializers.SerializerMethodField()
    covers_all_other_districts = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryZone
        fields = [
            "id", "name", "slug", "description", "charge",
            "estimated_days_min", "estimated_days_max", "estimated_days_label", "estimated_days",
            "free_shipping_threshold", "is_active", "sort_order", "is_default",
            "coverage", "covers_all_other_districts", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "estimated_days", "covers_all_other_districts", "created_at", "updated_at"]
        validators = []  # the case-insensitive name constraint is reported by `_save_or_conflict`
        # DRF turns the one-default-zone constraint (unique *where* is_default) into a plain unique
        # check that rejects any second `true`, which would forbid handing the default to another zone.
        # `services.save_zone` swaps the flag atomically and the database still enforces "at most one".
        extra_kwargs = {"is_default": {"validators": []}}

    def get_estimated_days(self, obj) -> str:
        return obj.estimated_days

    def get_covers_all_other_districts(self, obj) -> bool:
        return obj.is_default

    def validate_charge(self, value):
        return _charge(value)

    def validate_coverage(self, items):
        # On a PATCH (partial) DRF makes the nested serializer's fields optional too, so check here.
        if any("district_id" not in item for item in items):
            raise serializers.ValidationError("Every coverage entry needs a district_id.", code="required")
        return items

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        low = attrs.get("estimated_days_min", getattr(instance, "estimated_days_min", None))
        high = attrs.get("estimated_days_max", getattr(instance, "estimated_days_max", None))
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError({"estimated_days_max": ["Must be at least the minimum."]})
        return attrs

    def _save(self, zone, coverage):
        user = self.context["request"].user
        return self._save_or_conflict(lambda: services.save_zone(zone, coverage=coverage, user=user))

    def create(self, validated_data):
        coverage = validated_data.pop("coverage", None)
        return self._save(DeliveryZone(**validated_data), coverage)

    def update(self, instance, validated_data):
        coverage = validated_data.pop("coverage", None)
        for name, value in validated_data.items():
            setattr(instance, name, value)
        return self._save(instance, coverage)


class ZoneChargeSerializer(serializers.Serializer):
    charge = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_charge(self, value):
        return _charge(value)


class ChargeHistorySerializer(serializers.ModelSerializer):
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = ShippingChargeHistory
        fields = ["id", "zone", "zone_name", "old_charge", "new_charge", "changed_by", "created_at"]

    def get_changed_by(self, obj) -> dict | None:
        user = obj.changed_by
        return None if user is None else {"id": user.id, "full_name": user.full_name}


# --- admin: delivery methods ---------------------------------------------------------------------------


class AdminDeliveryMethodSerializer(SlugSerializerMixin, serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True, max_length=255)

    class Meta:
        model = DeliveryMethod
        fields = [
            "id", "name", "slug", "description", "extra_charge", "estimated_days_label",
            "is_active", "sort_order", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        validators = []

    def validate_extra_charge(self, value):
        return _charge(value)

    def create(self, validated_data):
        return self._save_or_conflict(lambda: super(AdminDeliveryMethodSerializer, self).create(validated_data))

    def update(self, instance, validated_data):
        return self._save_or_conflict(lambda: super(AdminDeliveryMethodSerializer, self).update(instance, validated_data))
