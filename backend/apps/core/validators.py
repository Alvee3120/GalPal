"""Reusable validators: image uploads and Bangladesh phone numbers."""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, URLValidator
from django.template.defaultfilters import filesizeformat
from PIL import Image, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}

_extension_validator = FileExtensionValidator(allowed_extensions=ALLOWED_IMAGE_EXTENSIONS)
_http_url = URLValidator(schemes=["http", "https"], message="Enter a valid http:// or https:// URL.")


def validate_http_url(value):
    """Only http(s) links: rejects javascript:, data:, ftp: and friends."""
    _http_url(value)


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


# --- video uploads -------------------------------------------------------------

ALLOWED_VIDEO_EXTENSIONS = ["mp4", "webm"]
_video_extension_validator = FileExtensionValidator(allowed_extensions=ALLOWED_VIDEO_EXTENSIONS)


def _sniff_video_format(header):
    """
    Identify a video by its magic bytes, the same spirit as Pillow's `Image.verify()` for
    images: a renamed non-video file with a `.mp4`/`.webm` extension is still rejected.

    WebM starts with the EBML header `1A 45 DF A3`. MP4 (ISO base media) has an `ftyp` box whose
    size varies, but it always appears at byte offset 4.
    """
    if header[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if header[4:8] == b"ftyp":
        return "mp4"
    return None


def validate_video_file(file):
    """
    Accept only mp4/webm videos up to `settings.VIDEO_MAX_UPLOAD_SIZE` bytes.

    Checked by extension, size, and a magic-byte sniff of the header (full decoding would need
    ffmpeg, which this project doesn't depend on).
    """
    _video_extension_validator(file)

    max_size = settings.VIDEO_MAX_UPLOAD_SIZE
    if file.size > max_size:
        raise ValidationError(
            f"Video is too large ({filesizeformat(file.size)}). "
            f"Maximum allowed size is {filesizeformat(max_size)}.",
            code="file_too_large",
        )

    try:
        file.seek(0)
        header = file.read(12)
    finally:
        file.seek(0)

    if _sniff_video_format(header) is None:
        raise ValidationError("Upload a valid MP4 or WebM video file.", code="invalid_video")


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
