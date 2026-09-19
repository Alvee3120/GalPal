import pytest
from django.core.exceptions import ValidationError

from apps.site_settings import validators as v


@pytest.mark.parametrize("value", ["#fff", "#FFF", "#d6336c", "#000000"])
def test_hex_color_accepts(value):
    v.validate_hex_color(value)


@pytest.mark.parametrize("value", ["fff", "#ff", "#ffff", "#gggggg", "red", "#12345", "#1234567", ""])
def test_hex_color_rejects(value):
    with pytest.raises(ValidationError):
        v.validate_hex_color(value)


def test_normalize_hex_color():
    assert v.normalize_hex_color("#abc") == "#AABBCC"
    assert v.normalize_hex_color("#d6336c") == "#D6336C"


@pytest.mark.parametrize(
    "validator,good,bad",
    [
        (v.validate_meta_pixel_id, ["123456789012345"], ["12345", "abc12345678", "1" * 21]),
        (v.validate_ga4_measurement_id, ["G-ABC123XYZ9"], ["ABC123", "G-", "g-abc123", "UA-1234-1"]),
        (v.validate_gtm_id, ["GTM-ABC1234"], ["ABC1234", "GTM-", "gtm-abc1234"]),
        (v.validate_tiktok_pixel_id, ["C4A1B2D3E4F5G6H7"], ["short", "has space here", "bad-chars!!"]),
    ],
)
def test_tracking_id_validators(validator, good, bad):
    for value in good:
        validator(value)
    for value in bad:
        with pytest.raises(ValidationError):
            validator(value)


@pytest.mark.parametrize("value", ["https://facebook.com/galpal", "http://example.com/x"])
def test_http_url_accepts(value):
    v.validate_http_url(value)


@pytest.mark.parametrize("value", ["javascript:alert(1)", "ftp://example.com", "data:text/html,x", "not a url", "//example.com"])
def test_http_url_rejects(value):
    with pytest.raises(ValidationError):
        v.validate_http_url(value)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("01712345678", "8801712345678"),
        ("+8801712345678", "8801712345678"),
        ("+880 1712-345678", "8801712345678"),
        ("8801712345678", "8801712345678"),
        ("+1 (415) 555-2671", "14155552671"),
        ("442071838750", "442071838750"),
    ],
)
def test_normalize_whatsapp_number(raw, expected):
    assert v.normalize_whatsapp_number(raw) == expected


@pytest.mark.parametrize("raw", ["123", "abcdefghijk", "+0123456789", "1" * 16, ""])
def test_normalize_whatsapp_number_rejects(raw):
    with pytest.raises(ValidationError):
        v.normalize_whatsapp_number(raw)
