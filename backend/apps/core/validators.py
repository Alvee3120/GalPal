"""Reusable validators: image uploads and Bangladesh phone numbers."""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.template.defaultfilters import filesizeformat
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

_extension_validator = FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)


def validate_image_file(file):
    """
    Accept only jpg/png/webp images up to `settings.IMAGE_MAX_UPLOAD_SIZE` bytes.

    The extension is checked first, then the actual bytes are opened with Pillow so a
    renamed non-image (or a GIF/BMP/SVG with a .png name) is rejected.
    """
    _extension_validator(file)

    max_size = settings.IMAGE_MAX_UPLOAD_SIZE
    if file.size > max_size:
        raise ValidationError(
            f"Image is too large ({filesizeformat(file.size)}). "
            f"Maximum allowed size is {filesizeformat(max_size)}.",
            code="file_too_large",
        )

    try:
        file.seek(0)
        with Image.open(file) as image:
            image_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError("Upload a valid image file.", code="invalid_image") from None
    finally:
        file.seek(0)

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError(
            "Unsupported image format. Allowed: JPG, PNG, WEBP.", code="invalid_image_format"
        )


# --- Bangladesh mobile numbers ------------------------------------------------

# Canonical form is the 11-digit local number: 01XXXXXXXXX (operator prefixes 013-019).
_BD_MOBILE = re.compile(r"^01[3-9]\d{8}$")


def normalize_bd_phone(value):
    """
    Return `value` as a canonical Bangladesh mobile number (`01712345678`).

    Accepts `01712345678`, `8801712345678`, `+8801712345678`, with spaces, dashes or
    brackets in between. Raises `ValidationError` for anything else.
    """
    digits = re.sub(r"[\s\-()]", "", str(value or ""))
    if digits.startswith("+880"):
        digits = "0" + digits[4:]
    elif digits.startswith("880") and len(digits) == 13:
        digits = "0" + digits[3:]
    if not _BD_MOBILE.match(digits):
        raise ValidationError(
            "Enter a valid Bangladesh mobile number, e.g. 01712345678.", code="invalid_phone"
        )
    return digits


def validate_bd_phone(value):
    """Model/serializer validator: the stored value must already be canonical."""
    if normalize_bd_phone(value) != value:
        raise ValidationError(
            "Enter a valid Bangladesh mobile number, e.g. 01712345678.", code="invalid_phone"
        )
