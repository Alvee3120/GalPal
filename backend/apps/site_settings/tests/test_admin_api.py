import io

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.site_settings.models import SiteSettings

pytestmark = pytest.mark.django_db

ADMIN = "/api/v1/admin/site-settings/"
TOKEN = "EAAB-super-secret-capi-token-1234567890"  # 38 chars
GA4 = "short-ga4"  # < 12 chars: fully masked


def png(name="a.png", fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "pink").save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue())


def patch(client, data, **kwargs):
    return client.patch(ADMIN, data, format=kwargs.pop("format", "json"), **kwargs)


# --- access control -------------------------------------------------------------------------------


def test_anonymous_is_401(api_client):
    assert api_client.get(ADMIN).status_code == 401
    assert api_client.patch(ADMIN, {}, format="json").status_code == 401


def test_customer_and_cce_are_403_on_get_and_patch(auth_client, customer, cce_user):
    for user in (customer, cce_user):
        client = auth_client(user)
        assert client.get(ADMIN).status_code == 403
        r = patch(client, {"site_name": "Hacked"})
        assert r.status_code == 403 and r.json()["error"]["code"] == "permission_denied"
    assert SiteSettings.objects.get().site_name == "GalPal"


def test_admin_can_read(auth_client, admin_user):
    r = auth_client(admin_user).get(ADMIN)
    assert r.status_code == 200 and r.json()["site_name"] == "GalPal"


def test_only_get_and_patch_are_supported(auth_client, admin_user):
    client = auth_client(admin_user)
    for method in ("post", "put", "delete"):
        assert getattr(client, method)(ADMIN, {}, format="json").status_code == 405
    assert SiteSettings.objects.count() == 1


# --- secrets are masked ---------------------------------------------------------------------------


def seed_secrets():
    row = SiteSettings.objects.get()
    row.meta_capi_access_token, row.ga4_api_secret = TOKEN, GA4
    row.save()


def test_admin_sees_secrets_masked_never_in_full(auth_client, admin_user):
    seed_secrets()
    response = auth_client(admin_user).get(ADMIN)
    body = response.json()
    assert body["meta_capi_access_token"] == "•" * 8 + TOKEN[-4:]
    assert body["ga4_api_secret"] == "•" * 8
    raw = response.content.decode()
    assert TOKEN not in raw and TOKEN[:-4] not in raw and GA4 not in raw


def test_unset_secret_reads_as_empty_string(auth_client, admin_user):
    body = auth_client(admin_user).get(ADMIN).json()
    assert body["meta_capi_access_token"] == "" and body["ga4_api_secret"] == ""


def test_patch_response_masks_the_secret_just_written(auth_client, admin_user):
    r = patch(auth_client(admin_user), {"meta_capi_access_token": "another-long-secret-token-5678"})
    assert r.json()["meta_capi_access_token"] == "•" * 8 + "5678"
    assert "another-long-secret-token" not in r.content.decode()
    assert SiteSettings.objects.get().meta_capi_access_token == "another-long-secret-token-5678"


def test_sending_the_masked_value_back_keeps_the_stored_secret(auth_client, admin_user):
    seed_secrets()
    client = auth_client(admin_user)
    form = client.get(ADMIN).json()  # what an admin form would resubmit untouched
    r = patch(client, {"meta_capi_access_token": form["meta_capi_access_token"], "ga4_api_secret": form["ga4_api_secret"], "tagline": "changed"})
    assert r.status_code == 200
    row = SiteSettings.objects.get()
    assert row.meta_capi_access_token == TOKEN and row.ga4_api_secret == GA4 and row.tagline == "changed"


def test_empty_string_clears_a_secret_and_a_new_value_replaces_it(auth_client, admin_user):
    seed_secrets()
    client = auth_client(admin_user)
    patch(client, {"ga4_api_secret": ""})
    assert SiteSettings.objects.get().ga4_api_secret == "" and SiteSettings.objects.get().meta_capi_access_token == TOKEN
    patch(client, {"meta_capi_access_token": "replacement-token-value-0000"})
    assert SiteSettings.objects.get().meta_capi_access_token == "replacement-token-value-0000"


def test_secret_fields_are_ignored_when_omitted(auth_client, admin_user):
    seed_secrets()
    patch(auth_client(admin_user), {"site_name": "Only this"})
    assert SiteSettings.objects.get().meta_capi_access_token == TOKEN


def test_test_event_code_and_flags_are_admin_visible(auth_client, admin_user):
    patch(auth_client(admin_user), {"meta_capi_test_event_code": "TEST123", "send_manual_orders_to_capi": True, "low_stock_threshold": 9})
    body = auth_client(admin_user).get(ADMIN).json()
    assert body["meta_capi_test_event_code"] == "TEST123"
    assert body["send_manual_orders_to_capi"] is True and body["low_stock_threshold"] == 9


# --- updating -------------------------------------------------------------------------------------


def test_patch_updates_only_the_sent_fields(auth_client, admin_user):
    r = patch(auth_client(admin_user), {"tagline": "Glow up", "phone": "09611-000000", "support_hours": "Sat-Thu 10-8"})
    assert r.status_code == 200
    row = SiteSettings.objects.get()
    assert (row.tagline, row.phone, row.site_name) == ("Glow up", "09611-000000", "GalPal")


def test_full_realistic_update(auth_client, admin_user):
    payload = {
        "site_name": "GalPal Beauty", "tagline": "Skincare you can trust", "primary_color": "#e91e63", "secondary_color": "#abc",
        "accent_color": "#FFC107", "text_color": "",
        "phone": "+880 9611-000000", "email": "care@galpal.example", "address": "House 1, Road 2, Dhanmondi, Dhaka",
        "whatsapp_number": "+880 1712-345678", "support_hours": "Sat-Thu 10am-8pm",
        "facebook_url": "https://facebook.com/galpal", "instagram_url": "https://instagram.com/galpal", "youtube_url": "https://youtube.com/@galpal",
        "tiktok_url": "https://tiktok.com/@galpal", "x_url": "https://x.com/galpal", "linkedin_url": "https://linkedin.com/company/galpal",
        "pinterest_url": "https://pinterest.com/galpal",
        "meta_pixel_id": "123456789012345", "ga4_measurement_id": "G-ABC123XYZ9", "gtm_id": "GTM-ABC1234", "tiktok_pixel_id": "C4A1B2D3E4F5G6H7",
        "custom_header_script": "<script>window.x=1</script>", "custom_footer_script": "<script>window.y=2</script>",
        "currency_code": "BDT", "currency_symbol": "৳", "tax_percent": "5.00", "free_shipping_threshold": "3000", "min_order_amount": "500",
        "guest_checkout_enabled": False, "allow_checkout_account_creation": False, "low_stock_threshold": 10, "maintenance_mode": True,
        "default_meta_title": "GalPal | Cosmetics & Skincare", "default_meta_description": "Authentic skincare delivered across Bangladesh.",
    }
    r = patch(auth_client(admin_user), payload)
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["primary_color"] == "#E91E63" and body["secondary_color"] == "#AABBCC" and body["text_color"] == ""
    assert body["whatsapp_number"] == "8801712345678"
    assert body["free_shipping_threshold"] == "3000.00" and body["tax_percent"] == "5.00" and body["min_order_amount"] == "500.00"
    assert body["guest_checkout_enabled"] is False and body["maintenance_mode"] is True
    row = SiteSettings.objects.get()
    assert row.custom_header_script == "<script>window.x=1</script>" and row.gtm_id == "GTM-ABC1234"


def test_updated_by_is_recorded_and_cannot_be_spoofed(auth_client, admin_user, cce_user):
    patch(auth_client(admin_user), {"site_name": "X", "updated_by": cce_user.id, "id": 99})
    row = SiteSettings.objects.get()
    assert row.updated_by == admin_user and row.pk == 1
    assert SiteSettings.objects.count() == 1


def test_updated_at_moves_forward(auth_client, admin_user):
    before = auth_client(admin_user).get(ADMIN).json()["updated_at"]
    after = patch(auth_client(admin_user), {"tagline": "later"}).json()["updated_at"]
    assert after > before


def test_admin_get_reads_the_live_row_not_the_cache(auth_client, admin_user, api_client):
    api_client.get("/api/v1/site-settings/")  # cache the row
    SiteSettings.objects.filter(pk=1).update(tagline="changed behind the cache's back")  # bypasses invalidation
    assert auth_client(admin_user).get(ADMIN).json()["tagline"] == "changed behind the cache's back"


@pytest.mark.parametrize("value,expected", [(None, None), ("", None), ("0", "0.00"), ("2500", "2500.00")])
def test_free_shipping_threshold_blank_or_zero_means_disabled(auth_client, admin_user, value, expected):
    r = patch(auth_client(admin_user), {"free_shipping_threshold": value})
    assert r.status_code == 200 and r.json()["free_shipping_threshold"] == expected
    assert SiteSettings.objects.get().free_shipping_enabled is bool(expected and expected != "0.00")


# --- validation -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("primary_color", "red"), ("primary_color", "#12"), ("primary_color", ""), ("secondary_color", "#GGGGGG"),
        ("accent_color", "blue"), ("text_color", "#12345"),
        ("meta_pixel_id", "abc"), ("ga4_measurement_id", "UA-123-1"), ("gtm_id", "GTM"), ("tiktok_pixel_id", "no spaces allowed"),
        ("facebook_url", "javascript:alert(1)"), ("instagram_url", "ftp://example.com"), ("youtube_url", "not a url"),
        ("x_url", "data:text/html,hi"), ("pinterest_url", "//evil.example"),
        ("email", "not-an-email"),
        ("tax_percent", "101"), ("tax_percent", "-1"), ("tax_percent", "abc"),
        ("free_shipping_threshold", "-5"), ("min_order_amount", "-1"), ("min_order_amount", "abc"),
        ("currency_code", "bdt"), ("currency_code", "BD"), ("currency_code", "BDTT"), ("currency_symbol", "TOOLONG"),
        ("whatsapp_number", "123"), ("whatsapp_number", "not a number"),
        ("low_stock_threshold", -1), ("low_stock_threshold", "abc"),
        ("site_name", ""), ("site_name", "x" * 101),
        ("default_meta_title", "x" * 71), ("default_meta_description", "x" * 321),
        ("custom_header_script", "x" * 20001), ("custom_footer_script", "x" * 20001),
        ("guest_checkout_enabled", "maybe"),
    ],
)
def test_invalid_values_are_rejected_with_a_field_error(auth_client, admin_user, field, value):
    r = patch(auth_client(admin_user), {field: value})
    assert r.status_code == 400, (field, value, r.json())
    assert r.json()["error"]["code"] == "validation_error" and field in r.json()["error"]["details"]
    assert SiteSettings.objects.get().site_name == "GalPal"  # nothing half-applied


def test_bad_url_is_reported_once_with_a_clear_message(auth_client, admin_user):
    r = patch(auth_client(admin_user), {"facebook_url": "javascript:alert(1)"})
    assert r.json()["error"]["details"]["facebook_url"] == ["Enter a valid http:// or https:// URL."]


def test_a_bad_field_prevents_the_whole_update(auth_client, admin_user):
    r = patch(auth_client(admin_user), {"tagline": "should not be saved", "primary_color": "nope"})
    assert r.status_code == 400
    assert SiteSettings.objects.get().tagline == ""


@pytest.mark.parametrize("field", ["accent_color", "text_color", "phone", "email", "whatsapp_number", "facebook_url", "meta_pixel_id", "tagline"])
def test_optional_fields_can_be_cleared(auth_client, admin_user, field):
    client = auth_client(admin_user)
    good = {"accent_color": "#FFC107", "text_color": "#111111", "phone": "123", "email": "a@b.co", "whatsapp_number": "01712345678",
            "facebook_url": "https://facebook.com/x", "meta_pixel_id": "123456789012", "tagline": "t"}[field]
    assert patch(client, {field: good}).status_code == 200
    r = patch(client, {field: ""})
    assert r.status_code == 200 and r.json()[field] == ""


def test_currency_can_change_but_stays_valid(auth_client, admin_user):
    r = patch(auth_client(admin_user), {"currency_code": "USD", "currency_symbol": "$"})
    assert r.status_code == 200 and (r.json()["currency_code"], r.json()["currency_symbol"]) == ("USD", "$")


# --- images ---------------------------------------------------------------------------------------


def test_upload_logo_favicon_and_og_image(auth_client, admin_user):
    r = patch(auth_client(admin_user), {"logo": png("logo.png"), "favicon": png("fav.png"), "default_og_image": png("og.png")}, format="multipart")
    assert r.status_code == 200
    for field in ("logo", "favicon", "default_og_image"):
        assert r.json()[field].startswith("http://testserver/media/branding/")
    assert default_storage.exists(SiteSettings.objects.get().logo.name)


def test_image_validation(auth_client, admin_user):
    client = auth_client(admin_user)
    gif = patch(client, {"logo": png("logo.gif", "GIF")}, format="multipart")
    assert gif.status_code == 400 and "logo" in gif.json()["error"]["details"]
    fake = patch(client, {"favicon": SimpleUploadedFile("f.png", b"<html>not an image</html>")}, format="multipart")
    assert fake.status_code == 400 and "favicon" in fake.json()["error"]["details"]


def test_oversized_image_is_rejected(auth_client, admin_user, settings):
    settings.IMAGE_MAX_UPLOAD_SIZE = 10
    r = patch(auth_client(admin_user), {"logo": png()}, format="multipart")
    assert r.status_code == 400 and "logo" in r.json()["error"]["details"]


def test_replacing_a_logo_deletes_the_old_file(auth_client, admin_user, django_capture_on_commit_callbacks):
    client = auth_client(admin_user)
    with django_capture_on_commit_callbacks(execute=True):
        patch(client, {"logo": png("one.png")}, format="multipart")
    old = SiteSettings.objects.get().logo.name
    with django_capture_on_commit_callbacks(execute=True):
        patch(client, {"logo": png("two.png")}, format="multipart")
    new = SiteSettings.objects.get().logo.name
    assert new != old and default_storage.exists(new) and not default_storage.exists(old)


def test_empty_value_removes_an_image(auth_client, admin_user, django_capture_on_commit_callbacks):
    client = auth_client(admin_user)
    with django_capture_on_commit_callbacks(execute=True):
        patch(client, {"logo": png()}, format="multipart")
    name = SiteSettings.objects.get().logo.name
    with django_capture_on_commit_callbacks(execute=True):
        r = patch(client, {"logo": ""}, format="multipart")
    assert r.status_code == 200 and r.json()["logo"] is None
    assert not SiteSettings.objects.get().logo and not default_storage.exists(name)


def test_patching_other_fields_leaves_images_alone(auth_client, admin_user):
    client = auth_client(admin_user)
    patch(client, {"logo": png()}, format="multipart")
    name = SiteSettings.objects.get().logo.name
    patch(client, {"tagline": "x"})
    assert SiteSettings.objects.get().logo.name == name


def test_multipart_update_without_booleans_does_not_reset_them(auth_client, admin_user):
    """Regression: DRF's BooleanField used to treat an absent multipart field as False."""
    client = auth_client(admin_user)
    patch(client, {"guest_checkout_enabled": False, "maintenance_mode": True})
    r = patch(client, {"logo": png("logo.png")}, format="multipart")
    assert r.status_code == 200
    assert r.json()["guest_checkout_enabled"] is False and r.json()["maintenance_mode"] is True
