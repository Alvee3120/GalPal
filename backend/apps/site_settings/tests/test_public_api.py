import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.site_settings.models import SiteSettings
from apps.site_settings.serializers import PRIVATE_FIELDS, PUBLIC_FIELDS, SECRET_FIELDS

pytestmark = pytest.mark.django_db

PUBLIC = "/api/v1/site-settings/"
ADMIN = "/api/v1/admin/site-settings/"

SECRETS = {
    "meta_capi_access_token": "EAAB-super-secret-capi-token-1234567890",
    "ga4_api_secret": "ga4-secret-abcdefghijkl",
    "meta_capi_test_event_code": "TEST-EVENT-98765",
}


def set_secrets():
    SiteSettings.objects.get()
    row = SiteSettings.objects.get()
    for name, value in SECRETS.items():
        setattr(row, name, value)
    row.send_manual_orders_to_capi = True
    row.low_stock_threshold = 7
    row.save()
    return row


def test_public_endpoint_is_open_to_guests(api_client):
    response = api_client.get(PUBLIC)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")


def test_stale_or_garbage_token_does_not_break_the_public_endpoint(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer expired.or.garbage")
    assert api_client.get(PUBLIC).status_code == 200


def test_public_payload_is_exactly_the_allow_list(api_client):
    assert set(api_client.get(PUBLIC).json()) == set(PUBLIC_FIELDS)


def test_secrets_never_appear_in_the_public_payload(api_client):
    set_secrets()
    response = api_client.get(PUBLIC)
    body = response.json()
    for field in PRIVATE_FIELDS:
        assert field not in body, field
    raw = response.content.decode()
    for value in SECRETS.values():
        assert value not in raw
        assert value[-6:] not in raw  # not even a fragment
    assert "updated_by" not in body and "id" not in body


def test_secrets_stay_out_of_public_output_even_after_an_admin_edit(api_client, auth_client, admin_user):
    auth_client(admin_user).patch(ADMIN, {"meta_capi_access_token": "brand-new-capi-token-xyz", "ga4_api_secret": "new-ga4-secret-value"}, format="json")
    raw = api_client.get(PUBLIC).content.decode()
    assert "brand-new-capi-token-xyz" not in raw and "new-ga4-secret-value" not in raw


def test_every_model_field_is_classified_public_private_or_internal():
    """A new SiteSettings field must be deliberately made public; it can't leak by default."""
    internal = {"id", "created_at", "updated_at", "updated_by"}
    fields = {f.name for f in SiteSettings._meta.get_fields()}
    assert fields == set(PUBLIC_FIELDS) | set(PRIVATE_FIELDS) | internal
    assert not set(PUBLIC_FIELDS) & set(PRIVATE_FIELDS)
    assert set(SECRET_FIELDS) <= set(PRIVATE_FIELDS)


def test_public_payload_has_expected_values_and_types(api_client):
    body = api_client.get(PUBLIC).json()
    assert body["site_name"] == "GalPal"
    assert body["currency_code"] == "BDT" and body["currency_symbol"] == "৳"
    assert body["guest_checkout_enabled"] is True and body["allow_checkout_account_creation"] is True
    assert body["maintenance_mode"] is False
    assert body["min_order_amount"] == "0.00"  # money is a decimal string, never a float
    assert body["tax_percent"] is None and body["free_shipping_threshold"] is None
    assert body["logo"] is None and body["favicon"] is None and body["default_og_image"] is None


def test_public_commerce_values_are_decimal_strings(api_client):
    row = SiteSettings.objects.get()
    row.free_shipping_threshold, row.tax_percent, row.min_order_amount = "2500", "7.5", "300"
    row.save()
    body = api_client.get(PUBLIC).json()
    assert (body["free_shipping_threshold"], body["tax_percent"], body["min_order_amount"]) == ("2500.00", "7.50", "300.00")


def test_public_images_are_absolute_urls(api_client):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, format="PNG")
    row = SiteSettings.objects.get()
    row.logo = SimpleUploadedFile("logo.png", buffer.getvalue())
    row.save()
    logo = api_client.get(PUBLIC).json()["logo"]
    assert logo.startswith("http://testserver/media/branding/") and logo.endswith(".png")


def test_public_endpoint_is_read_only(api_client, auth_client, admin_user):
    for client in (api_client, auth_client(admin_user)):
        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)(PUBLIC, {}, format="json").status_code == 405


def test_public_endpoint_is_served_from_cache(api_client, django_assert_max_num_queries):
    api_client.get(PUBLIC)
    with django_assert_max_num_queries(0):
        assert api_client.get(PUBLIC).status_code == 200


def test_admin_changes_show_up_publicly_right_away(api_client, auth_client, admin_user):
    assert api_client.get(PUBLIC).json()["maintenance_mode"] is False  # primes the cache
    auth_client(admin_user).patch(ADMIN, {"maintenance_mode": True, "site_name": "গালপাল"}, format="json")
    body = api_client.get(PUBLIC).json()
    assert body["maintenance_mode"] is True and body["site_name"] == "গালপাল"
