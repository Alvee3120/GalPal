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
