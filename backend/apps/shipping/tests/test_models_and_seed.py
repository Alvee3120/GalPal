import importlib
from decimal import Decimal
from io import StringIO

import pytest
from django.apps import apps as django_apps
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.shipping import seed
from apps.shipping.models import (
    DeliveryMethod,
    DeliveryZone,
    District,
    ShippingChargeHistory,
    ZoneDistrict,
    format_estimated_days,
)

from .factories import DeliveryMethodFactory, DeliveryZoneFactory, district

pytestmark = pytest.mark.django_db


# --- districts -----------------------------------------------------------------------------------------


def test_there_are_exactly_64_districts_in_8_divisions():
    assert District.objects.count() == 64
    assert District.objects.values("division").distinct().count() == 8
    assert District.objects.filter(division="Dhaka").count() == 13
    assert District.objects.filter(division="Chattogram").count() == 11


def test_district_names_and_slugs_are_unique_and_common_spellings_are_aliases():
    assert len(set(District.objects.values_list("slug", flat=True))) == 64
    assert "Chittagong" in district("Chattogram").aliases
    assert "Comilla" in district("Cumilla").aliases


def test_seeding_districts_twice_creates_nothing_new():
    assert seed.seed_districts(District) == 0
    assert District.objects.count() == 64


# --- default data --------------------------------------------------------------------------------------


def test_seeded_defaults_are_70_inside_and_120_outside(seeded):
    assert seeded["inside-dhaka"].charge == Decimal("70.00")
    assert seeded["outside-dhaka"].charge == Decimal("120.00")


def test_outside_dhaka_is_the_only_default_and_inside_dhaka_covers_dhaka(seeded):
    assert list(DeliveryZone.objects.filter(is_default=True)) == [seeded["outside-dhaka"]]
    links = ZoneDistrict.objects.filter(zone=seeded["inside-dhaka"])
    assert [(l.district.name, l.areas) for l in links] == [("Dhaka", [])]
    assert not seeded["outside-dhaka"].coverage.exists()  # the default covers "everything else" by definition


def test_seeded_methods_standard_is_on_express_is_off(seeded):
    standard, express = DeliveryMethod.objects.get(slug="standard"), DeliveryMethod.objects.get(slug="express")
    assert standard.is_active and standard.extra_charge == 0
    assert not express.is_active and express.extra_charge == Decimal("100.00")


def test_the_starting_charges_are_in_the_charge_history(seeded):
    rows = ShippingChargeHistory.objects.order_by("id")
    assert [(r.zone_name, r.old_charge, r.new_charge) for r in rows] == [
        ("Inside Dhaka", None, Decimal("70.00")), ("Outside Dhaka", None, Decimal("120.00")),
    ]


def test_seeding_is_idempotent(seeded):
    before = (DeliveryZone.objects.count(), DeliveryMethod.objects.count(), ZoneDistrict.objects.count(),
              ShippingChargeHistory.objects.count())
    result = seed.seed_all(District, DeliveryZone, ZoneDistrict, DeliveryMethod, ShippingChargeHistory)
    assert result == {"districts": 0, "zones": [], "methods": []}
    assert before == (DeliveryZone.objects.count(), DeliveryMethod.objects.count(), ZoneDistrict.objects.count(),
                      ShippingChargeHistory.objects.count())


def test_reseeding_never_overwrites_an_admin_edited_charge(seeded):
    DeliveryZone.objects.filter(slug="inside-dhaka").update(charge="99.00", name="Dhaka City")
    seed.seed_all(District, DeliveryZone, ZoneDistrict, DeliveryMethod, ShippingChargeHistory)
    zone = DeliveryZone.objects.get(slug="inside-dhaka")
    assert zone.charge == Decimal("99.00") and zone.name == "Dhaka City"
    assert DeliveryZone.objects.count() == 2


def test_reseeding_does_not_add_a_second_default_when_the_admin_picked_another(seeded):
    other = DeliveryZoneFactory(name="Everywhere else")
    DeliveryZone.objects.filter(is_default=True).update(is_default=False)
    DeliveryZone.objects.filter(pk=other.pk).update(is_default=True)
    DeliveryZone.objects.filter(slug="outside-dhaka").delete()
    seed.seed_all(District, DeliveryZone, ZoneDistrict, DeliveryMethod, ShippingChargeHistory)
    assert list(DeliveryZone.objects.filter(is_default=True)) == [other]


def test_the_data_migration_function_seeds_an_empty_database():
    DeliveryZone.objects.all().delete()
    DeliveryMethod.objects.all().delete()
    District.objects.all().delete()
    module = importlib.import_module("apps.shipping.migrations.0002_seed_defaults")
    module.seed_defaults(django_apps, None)
    assert District.objects.count() == 64
    assert {z.slug: z.charge for z in DeliveryZone.objects.all()} == {
        "inside-dhaka": Decimal("70.00"), "outside-dhaka": Decimal("120.00")}
    module.seed_defaults(django_apps, None)  # and it is safe to run twice
    assert District.objects.count() == 64 and DeliveryZone.objects.count() == 2


def test_the_management_command_seeds_and_reports_and_is_rerunnable():
    out = StringIO()
    call_command("seed_shipping", stdout=out)
    assert DeliveryZone.objects.count() == 2 and "Inside Dhaka" in out.getvalue()
    out = StringIO()
    call_command("seed_shipping", stdout=out)
    assert "Zones created: none" in out.getvalue() and DeliveryZone.objects.count() == 2


def test_reset_charges_restores_70_and_120_and_logs_it(seeded):
    DeliveryZone.objects.filter(slug="inside-dhaka").update(charge="55.00")
    call_command("seed_shipping", "--reset-charges", stdout=StringIO())
    assert DeliveryZone.objects.get(slug="inside-dhaka").charge == Decimal("70.00")
    last = ShippingChargeHistory.objects.filter(zone__slug="inside-dhaka").first()
    assert (last.old_charge, last.new_charge) == (Decimal("55.00"), Decimal("70.00"))


def test_the_command_without_the_flag_leaves_edited_charges_alone(seeded):
    DeliveryZone.objects.filter(slug="inside-dhaka").update(charge="55.00")
    call_command("seed_shipping", stdout=StringIO())
    assert DeliveryZone.objects.get(slug="inside-dhaka").charge == Decimal("55.00")


# --- database constraints ------------------------------------------------------------------------------


def fails(**kwargs):
    with pytest.raises(IntegrityError), transaction.atomic():
        DeliveryZoneFactory(**kwargs)


def test_only_one_zone_can_be_default():
    DeliveryZoneFactory(is_default=True)
    fails(is_default=True)


def test_a_default_zone_cannot_be_inactive():
    fails(is_default=True, is_active=False)


def test_a_charge_cannot_be_negative_at_the_database_level():
    fails(charge="-1.00")


def test_zone_names_are_unique_ignoring_case():
    DeliveryZoneFactory(name="Dhaka Metro")
    fails(name="dhaka metro")


def test_the_estimate_range_must_be_ordered():
    fails(estimated_days_min=5, estimated_days_max=2)


def test_a_threshold_cannot_be_negative():
    fails(free_shipping_threshold="-5.00")


def test_a_district_has_only_one_whole_district_zone():
    a, b = DeliveryZoneFactory(), DeliveryZoneFactory()
    ZoneDistrict.objects.create(zone=a, district=district("Sylhet"), areas=[])
    with pytest.raises(IntegrityError), transaction.atomic():
        ZoneDistrict.objects.create(zone=b, district=district("Sylhet"), areas=[])


def test_two_zones_may_each_take_areas_of_the_same_district():
    a, b = DeliveryZoneFactory(), DeliveryZoneFactory()
    ZoneDistrict.objects.create(zone=a, district=district("Dhaka"), areas=["Mirpur"])
    ZoneDistrict.objects.create(zone=b, district=district("Dhaka"), areas=["Savar"])
    ZoneDistrict.objects.create(zone=DeliveryZoneFactory(), district=district("Dhaka"), areas=[])


def test_a_zone_lists_a_district_once():
    zone = DeliveryZoneFactory()
    ZoneDistrict.objects.create(zone=zone, district=district("Dhaka"), areas=["Mirpur"])
    with pytest.raises(IntegrityError), transaction.atomic():
        ZoneDistrict.objects.create(zone=zone, district=district("Dhaka"), areas=["Savar"])


def test_method_names_are_unique_ignoring_case_and_extra_cannot_be_negative():
    DeliveryMethodFactory(name="Express")
    with pytest.raises(IntegrityError), transaction.atomic():
        DeliveryMethodFactory(name="EXPRESS")
    with pytest.raises(IntegrityError), transaction.atomic():
        DeliveryMethodFactory(extra_charge="-1.00")


def test_methods_are_inactive_by_default():
    assert DeliveryMethod.objects.create(name="Drone", slug="drone", extra_charge="10").is_active is False


def test_deleting_a_zone_keeps_its_history_with_the_name():
    zone = DeliveryZoneFactory(name="Temp")
    ShippingChargeHistory.objects.create(zone=zone, zone_name="Temp", old_charge=None, new_charge="10.00")
    zone.delete()
    row = ShippingChargeHistory.objects.get()
    assert row.zone is None and row.zone_name == "Temp"


@pytest.mark.parametrize(("low", "high", "label", "text"), [
    (1, 2, "", "1-2 days"), (3, 3, "", "3 days"), (1, 1, "", "1 day"), (2, None, "", "2 days"),
    (None, 4, "", "4 days"), (None, None, "", ""), (1, 2, "Same day", "Same day"),
])
def test_estimated_days_text(low, high, label, text):
    assert format_estimated_days(low, high, label) == text
