import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.core.validators import validate_image_file


def make_image(fmt="PNG", name="pic.png", size=(4, 4)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "pink").save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue())


@pytest.mark.parametrize(
    "fmt,name", [("PNG", "a.png"), ("JPEG", "a.jpg"), ("JPEG", "a.jpeg"), ("WEBP", "a.webp")]
)
def test_accepts_allowed_formats(fmt, name):
    file = make_image(fmt, name)
    validate_image_file(file)
    assert file.read(4)  # stream was rewound for the caller


def test_rejects_gif_even_with_allowed_extension():
    with pytest.raises(ValidationError) as exc:
        validate_image_file(make_image("GIF", "sneaky.png"))
    assert exc.value.code == "invalid_image_format"


def test_rejects_disallowed_extension():
    with pytest.raises(ValidationError) as exc:
        validate_image_file(make_image("PNG", "a.gif"))
    assert exc.value.code == "invalid_extension"


def test_rejects_non_image_bytes():
    fake = SimpleUploadedFile("evil.png", b"<html>not an image</html>")
    with pytest.raises(ValidationError) as exc:
        validate_image_file(fake)
    assert exc.value.code == "invalid_image"


def test_rejects_oversized_image(settings):
    settings.IMAGE_MAX_UPLOAD_SIZE = 10
    with pytest.raises(ValidationError) as exc:
        validate_image_file(make_image())
    assert exc.value.code == "file_too_large"


# --- Bangladesh phone numbers -------------------------------------------------

from apps.core.validators import normalize_bd_phone, validate_bd_phone  # noqa: E402


@pytest.mark.parametrize(
    "raw",
    ["01712345678", "+8801712345678", "8801712345678", "+880 1712-345678", " 017 1234 5678 ", "(01712) 345678"],
)
def test_normalize_bd_phone_accepts_common_formats(raw):
    assert normalize_bd_phone(raw) == "01712345678"


@pytest.mark.parametrize(
    "raw", ["", None, "1712345678", "0171234567", "017123456789", "01212345678", "01012345678",
            "+8801212345678", "+919812345678", "abcdefghijk", "88017123456789"],
)
def test_normalize_bd_phone_rejects_bad_numbers(raw):
    with pytest.raises(ValidationError) as exc:
        normalize_bd_phone(raw)
    assert exc.value.code == "invalid_phone"


def test_validate_bd_phone_requires_canonical_form():
    validate_bd_phone("01712345678")
    with pytest.raises(ValidationError):
        validate_bd_phone("+8801712345678")
