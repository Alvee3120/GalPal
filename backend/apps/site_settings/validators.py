"""Field validators for the site settings (each is also usable from the Django admin)."""

import re

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from apps.core.validators import normalize_bd_phone, validate_http_url  # noqa: F401 (re-exported)

validate_hex_color = RegexValidator(
    r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$",
    "Enter a hex colour such as #D6336C or #FFF.",
    code="invalid_color",
)

validate_meta_pixel_id = RegexValidator(r"^\d{8,20}$", "A Meta Pixel ID is 8-20 digits.", code="invalid_pixel_id")
validate_ga4_measurement_id = RegexValidator(
    r"^G-[A-Z0-9]{4,20}$", "A GA4 measurement ID looks like G-XXXXXXXXXX.", code="invalid_ga4_id"
)
validate_gtm_id = RegexValidator(r"^GTM-[A-Z0-9]{4,12}$", "A GTM container ID looks like GTM-XXXXXXX.", code="invalid_gtm_id")
validate_tiktok_pixel_id = RegexValidator(
    r"^[A-Za-z0-9]{8,32}$", "A TikTok pixel ID is 8-32 letters/digits.", code="invalid_tiktok_pixel_id"
)

def normalize_hex_color(value):
    """`#abc` -> `#AABBCC`, `#d6336c` -> `#D6336C`. Assumes the value passed `validate_hex_color`."""
    value = value.upper()
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    return value


def normalize_whatsapp_number(value):
    """
    Digits-only international number, ready for `https://wa.me/<number>`.

    Bangladesh numbers in any local/international format become `8801XXXXXXXXX`; other countries
    are accepted as E.164 (8-15 digits, optional leading +).
    """
    try:
        return "88" + normalize_bd_phone(value)
    except ValidationError:
        pass
    digits = re.sub(r"[\s\-()]", "", str(value))
    digits = digits[1:] if digits.startswith("+") else digits
    if not re.fullmatch(r"[1-9]\d{7,14}", digits):
        raise ValidationError(
            "Enter a valid WhatsApp number with country code, e.g. +8801712345678.", code="invalid_whatsapp"
        )
    return digits
