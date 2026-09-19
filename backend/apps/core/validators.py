"""Reusable upload validators."""

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
