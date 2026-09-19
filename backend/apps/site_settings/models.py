from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.core.utils import UploadPath
from apps.core.validators import validate_image_file

from . import validators as v

MONEY = {"max_digits": 12, "decimal_places": 2}
_min_zero = MinValueValidator(0)


def _image(help_text=""):
    return models.ImageField(
        upload_to=UploadPath("branding"), validators=[validate_image_file], null=True, blank=True, help_text=help_text
    )


class HttpURLField(models.URLField):
    """A URLField that accepts only http(s) links (and reports a bad one once, not twice)."""

    default_validators = [v.validate_http_url]


def _social(label):
    return HttpURLField(max_length=300, blank=True, help_text=f"{label} page URL")


class SiteSettings(TimeStampedModel):
    """
    The one and only row of global site settings (always `id=1`).

    Read it with `apps.site_settings.services.get_site_settings()` (cached); never query the
    model directly in request paths. Delivery charges are NOT stored here, they live in the
    Module 9 delivery zones.
    """

    # --- Branding ------------------------------------------------------------
    site_name = models.CharField(max_length=100, default="GalPal")
    logo = _image()
    favicon = _image("PNG/JPG/WEBP")
    tagline = models.CharField(max_length=200, blank=True)
    primary_color = models.CharField(max_length=7, default="#D6336C", validators=[v.validate_hex_color])
    secondary_color = models.CharField(max_length=7, default="#FFF0F6", validators=[v.validate_hex_color])
    accent_color = models.CharField(max_length=7, blank=True, validators=[v.validate_hex_color])
    text_color = models.CharField(max_length=7, blank=True, validators=[v.validate_hex_color])

    # --- Contact -------------------------------------------------------------
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    whatsapp_number = models.CharField(
        max_length=20, blank=True, help_text="Digits only with country code, e.g. 8801712345678"
    )
    support_hours = models.CharField(max_length=200, blank=True, help_text="e.g. Sat-Thu, 10am-8pm")

    # --- Social links --------------------------------------------------------
    facebook_url = _social("Facebook")
    instagram_url = _social("Instagram")
    youtube_url = _social("YouTube")
    tiktok_url = _social("TikTok")
    x_url = _social("X (Twitter)")
    linkedin_url = _social("LinkedIn")
    pinterest_url = _social("Pinterest")

    # --- Marketing / tracking ------------------------------------------------
    meta_pixel_id = models.CharField(max_length=20, blank=True, validators=[v.validate_meta_pixel_id])
    meta_capi_access_token = models.CharField(max_length=500, blank=True, help_text="SECRET: Meta Conversions API token")
    meta_capi_test_event_code = models.CharField(max_length=50, blank=True, help_text="Server-only")
    ga4_measurement_id = models.CharField(max_length=22, blank=True, validators=[v.validate_ga4_measurement_id])
    ga4_api_secret = models.CharField(max_length=200, blank=True, help_text="SECRET: GA4 Measurement Protocol API secret")
    gtm_id = models.CharField(max_length=14, blank=True, validators=[v.validate_gtm_id])
    tiktok_pixel_id = models.CharField(max_length=32, blank=True, validators=[v.validate_tiktok_pixel_id])
    custom_header_script = models.TextField(blank=True, max_length=20000, help_text="Injected into <head> by the storefront")
    custom_footer_script = models.TextField(blank=True, max_length=20000, help_text="Injected before </body> by the storefront")
    send_manual_orders_to_capi = models.BooleanField(default=False)

    # --- Commerce ------------------------------------------------------------
    currency_code = models.CharField(
        max_length=3, default="BDT", validators=[RegexValidator(r"^[A-Z]{3}$", "Use a 3-letter ISO code, e.g. BDT.")]
    )
    currency_symbol = models.CharField(max_length=5, default="৳")
    tax_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, validators=[_min_zero, MaxValueValidator(100)],
        help_text="VAT/tax % added to orders. Blank or 0 = no tax.",
    )
    free_shipping_threshold = models.DecimalField(
        **MONEY, null=True, blank=True, validators=[_min_zero],
        help_text="Subtotal at which shipping becomes free. Blank or 0 = disabled. A delivery zone can override it.",
    )
    min_order_amount = models.DecimalField(**MONEY, default=0, validators=[_min_zero])
    guest_checkout_enabled = models.BooleanField(default=True)
    allow_checkout_account_creation = models.BooleanField(
        default=True, help_text='Allow "save my details" account creation at guest checkout'
    )
    low_stock_threshold = models.PositiveIntegerField(default=5)
    maintenance_mode = models.BooleanField(default=False)

    # --- SEO defaults --------------------------------------------------------
    default_meta_title = models.CharField(max_length=70, blank=True)
    default_meta_description = models.CharField(max_length=320, blank=True)
    default_og_image = _image("Default social-share image")

    # --- Audit ---------------------------------------------------------------
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"
        constraints = [
            # Enforced in the database, not just in Python.
            models.CheckConstraint(condition=Q(id=1), name="site_settings_single_row"),
        ]

    def __str__(self):
        return f"Site settings ({self.site_name})"

    def save(self, *args, **kwargs):
        self.pk = self.id = 1
        kwargs.pop("force_insert", None)  # `create()` on the singleton behaves as an upsert
        if self._state.adding:
            # A fresh instance replaces the existing row via UPDATE, which would null created_at
            # (auto_now_add only fires on INSERT), so carry the original value over.
            existing = type(self).objects.filter(pk=1).values_list("created_at", flat=True).first()
            if existing:
                self.created_at = existing
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("The site settings row cannot be deleted.", code="protected")

    @property
    def free_shipping_enabled(self):
        return bool(self.free_shipping_threshold and self.free_shipping_threshold > 0)
