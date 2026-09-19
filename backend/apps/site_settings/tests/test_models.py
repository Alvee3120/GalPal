from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.site_settings.models import SiteSettings

pytestmark = pytest.mark.django_db


def test_default_row_is_created_by_the_migration():
    row = SiteSettings.objects.get()
    assert row.pk == 1 and row.site_name == "GalPal"


def test_defaults():
    row = SiteSettings.objects.get()
    assert (row.currency_code, row.currency_symbol) == ("BDT", "৳")
    assert row.guest_checkout_enabled is True
    assert row.allow_checkout_account_creation is True
    assert row.send_manual_orders_to_capi is False
    assert row.maintenance_mode is False
    assert row.min_order_amount == 0 and row.tax_percent is None and row.free_shipping_threshold is None
    assert row.low_stock_threshold == 5
    assert row.primary_color and row.secondary_color
    assert row.meta_capi_access_token == "" and row.ga4_api_secret == ""


def test_only_one_row_can_ever_exist_via_the_orm():
    SiteSettings.objects.create(site_name="Created")  # behaves as an upsert of the singleton
    SiteSettings(site_name="Another").save()
    assert SiteSettings.objects.count() == 1
    assert SiteSettings.objects.get().site_name == "Another"
    assert SiteSettings.objects.get().pk == 1


def test_replacing_the_singleton_keeps_its_original_created_at():
    original = SiteSettings.objects.get().created_at
    SiteSettings(site_name="Replacement").save()
    row = SiteSettings.objects.get()
    assert row.created_at == original and row.updated_at >= original


def test_database_itself_rejects_a_second_row():
    with pytest.raises(IntegrityError), transaction.atomic():
        SiteSettings.objects.bulk_create([SiteSettings(id=2)])  # bulk_create skips save()
    assert SiteSettings.objects.count() == 1


def test_instance_delete_is_refused():
    with pytest.raises(ValidationError) as exc:
        SiteSettings.objects.get().delete()
    assert exc.value.code == "protected"
    assert SiteSettings.objects.count() == 1


def test_free_shipping_enabled_treats_blank_and_zero_as_disabled():
    row = SiteSettings.objects.get()
    for value, expected in [(None, False), (Decimal("0"), False), (Decimal("0.00"), False), (Decimal("1500"), True), (Decimal("999.50"), True)]:
        row.free_shipping_threshold = value
        assert row.free_shipping_enabled is expected


def test_full_clean_runs_the_field_validators():
    row = SiteSettings.objects.get()
    row.primary_color = "pink"
    row.meta_pixel_id = "abc"
    row.facebook_url = "javascript:alert(1)"
    row.tax_percent = 150
    with pytest.raises(ValidationError) as exc:
        row.full_clean()
    assert set(exc.value.message_dict) >= {"primary_color", "meta_pixel_id", "facebook_url", "tax_percent"}


def test_str():
    assert str(SiteSettings.objects.get()) == "Site settings (GalPal)"
