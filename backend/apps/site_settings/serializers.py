from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from rest_framework import serializers
from rest_framework.fields import SkipField

from apps.core.utils import is_masked, mask_secret

from . import services, validators as v
from .models import HttpURLField, SiteSettings

# The public endpoint is an ALLOW-list: a new model field stays private until added here.
PUBLIC_FIELDS = [
    # branding
    "site_name", "logo", "favicon", "tagline", "primary_color", "secondary_color", "accent_color", "text_color",
    # contact
    "phone", "email", "address", "whatsapp_number", "support_hours",
    # social
    "facebook_url", "instagram_url", "youtube_url", "tiktok_url", "x_url", "linkedin_url", "pinterest_url",
    # tracking (public IDs and scripts the storefront must render)
    "meta_pixel_id", "ga4_measurement_id", "gtm_id", "tiktok_pixel_id", "custom_header_script", "custom_footer_script",
    # commerce
    "currency_code", "currency_symbol", "tax_percent", "free_shipping_threshold", "min_order_amount",
    "guest_checkout_enabled", "allow_checkout_account_creation", "maintenance_mode",
    # seo
    "default_meta_title", "default_meta_description", "default_og_image",
]

SECRET_FIELDS = ["meta_capi_access_token", "ga4_api_secret"]
# Admin-only, never public
PRIVATE_FIELDS = [*SECRET_FIELDS, "meta_capi_test_event_code", "send_manual_orders_to_capi", "low_stock_threshold"]


class HttpURLSerializerField(serializers.URLField):
    """DRF's URLField bolts on its own URLValidator; drop it so the http(s)-only rule reports once."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validators = [x for x in self.validators if not isinstance(x, URLValidator)]


class HexColorField(serializers.CharField):
    """Validates a hex colour and stores it as upper-case 6-digit `#RRGGBB`."""

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            v.validate_hex_color(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from None
        return v.normalize_hex_color(value)


class SecretField(serializers.CharField):
    """
    Write-only-in-practice: reads return a masked value, writes accept a new secret.

    Sending the masked value back unchanged (what a form does when the admin didn't touch the
    field) keeps the stored secret; sending "" clears it.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_blank", True)
        super().__init__(**kwargs)

    def to_representation(self, value):
        return mask_secret(value)

    def to_internal_value(self, data):
        if is_masked(data):
            raise SkipField()
        return super().to_internal_value(data)


class PublicSiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = PUBLIC_FIELDS
        read_only_fields = fields


class AdminSiteSettingsSerializer(serializers.ModelSerializer):
    serializer_field_mapping = {**serializers.ModelSerializer.serializer_field_mapping, HttpURLField: HttpURLSerializerField}

    primary_color = HexColorField(max_length=7, required=False)
    secondary_color = HexColorField(max_length=7, required=False)
    accent_color = HexColorField(max_length=7, required=False, allow_blank=True)
    text_color = HexColorField(max_length=7, required=False, allow_blank=True)
    meta_capi_access_token = SecretField(max_length=500, help_text="Masked on read. Send a new value to replace it, or an empty string to clear it.")
    ga4_api_secret = SecretField(max_length=200, help_text="Masked on read. Send a new value to replace it, or an empty string to clear it.")

    class Meta:
        model = SiteSettings
        fields = [*PUBLIC_FIELDS, *PRIVATE_FIELDS, "updated_at"]
        read_only_fields = ["updated_at"]
        extra_kwargs = {"whatsapp_number": {"help_text": "Any format; stored as digits with country code."}}

    def validate_whatsapp_number(self, value):
        if not value:
            return ""
        try:
            return v.normalize_whatsapp_number(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from None

    def update(self, instance, validated_data):
        return services.update_site_settings(instance, user=self.context["request"].user, **validated_data)
