from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError

from apps.shipping import services
from apps.shipping.exceptions import ShippingNotConfigured
from apps.shipping.models import DeliveryMethod, DeliveryZone, ShippingChargeHistory, ZoneDistrict
from apps.site_settings.models import SiteSettings

from .factories import DeliveryMethodFactory, DeliveryZoneFactory, cover, district

pytestmark = pytest.mark.django_db

D = Decimal


def set_global_threshold(value):
    row, _ = SiteSettings.objects.get_or_create(id=1)
    row.free_shipping_threshold = value
    row.save()


def quote(district_name="Dhaka", subtotal="500", coupon=None, area="", method=None):
    return services.calculate_shipping({"district": district_name, "area": area}, D(subtotal), coupon, delivery_method=method)


# --- text normalisation -----------------------------------------------------------------------------------


@pytest.mark.parametrize(("raw", "expected"), [
    ("Dhaka", "dhaka"), ("  DHAKA  ", "dhaka"), ("Dhaka District", "dhaka"), ("Cox's Bazar", "coxs bazar"),
    ("Cox’s  Bazar", "coxs bazar"), ("Chapai-Nawabganj", "chapai nawabganj"), (None, ""), ("", ""),
])
def test_normalize_name(raw, expected):
    assert services.normalize_name(raw) == expected


# --- resolving a zone ---------------------------------------------------------------------------------------


def test_a_covered_district_gets_its_zone_and_everything_else_the_default(seeded):
    assert services.resolve_zone("Dhaka")["name"] == "Inside Dhaka"
    assert services.resolve_zone("Sylhet")["name"] == "Outside Dhaka"
    assert services.resolve_zone("Chattogram")["name"] == "Outside Dhaka"


@pytest.mark.parametrize("spelling", ["dhaka", "DHAKA", " Dhaka ", "Dhaka District"])
def test_district_matching_ignores_case_spacing_and_the_word_district(seeded, spelling):
    assert services.resolve_zone(spelling)["name"] == "Inside Dhaka"


def test_alternative_spellings_of_a_district_match_its_zone():
    zone = DeliveryZoneFactory(name="Port City")
    cover(zone, "Chattogram")
    DeliveryZoneFactory(name="Rest", is_default=True)
    assert services.resolve_zone("Chittagong")["name"] == "Port City"
    assert services.resolve_zone("chattogram")["name"] == "Port City"


def test_an_unknown_or_blank_district_falls_back_to_the_default(seeded):
    for value in ("Atlantis", "", None, "   "):
        assert services.resolve_zone(value)["name"] == "Outside Dhaka"


def test_a_zone_naming_the_area_beats_the_whole_district_zone():
    city = DeliveryZoneFactory(name="Dhaka City", charge="60.00")
    outer = DeliveryZoneFactory(name="Outer Dhaka", charge="90.00")
    DeliveryZoneFactory(name="Rest", is_default=True)
    cover(city, "Dhaka", areas=["Mirpur", "Dhanmondi", "Gulshan"])
    cover(outer, "Dhaka")
    assert services.resolve_zone("Dhaka", "Mirpur")["name"] == "Dhaka City"
    assert services.resolve_zone("Dhaka", " dhanmondi ")["name"] == "Dhaka City"
    assert services.resolve_zone("Dhaka", "Savar")["name"] == "Outer Dhaka"
    assert services.resolve_zone("Dhaka", "")["name"] == "Outer Dhaka"


def test_a_district_with_only_area_rules_sends_other_areas_to_the_default():
    city = DeliveryZoneFactory(name="Dhaka City")
    DeliveryZoneFactory(name="Rest", is_default=True)
    cover(city, "Dhaka", areas=["Mirpur"])
    assert services.resolve_zone("Dhaka", "Mirpur")["name"] == "Dhaka City"
    assert services.resolve_zone("Dhaka", "Savar")["name"] == "Rest"


def test_an_inactive_zone_is_ignored_and_its_districts_fall_back(seeded):
    DeliveryZone.objects.filter(slug="inside-dhaka").update(is_active=False)
    assert services.resolve_zone("Dhaka")["name"] == "Outside Dhaka"


def test_with_no_default_zone_it_fails_loudly_not_silently():
    DeliveryZoneFactory()
    with pytest.raises(ShippingNotConfigured):
        services.resolve_zone("Sylhet")


# --- the calculation: the spec's five steps ----------------------------------------------------------------------


def test_the_result_has_the_documented_shape(seeded):
    result = quote("Dhaka")
    assert {"zone_id", "zone_name", "charge", "is_free", "free_shipping_reason", "estimated_days"} <= set(result)
    assert result["zone_id"] == seeded["inside-dhaka"].id and result["zone_name"] == "Inside Dhaka"
    assert result["charge"] == D("70.00") and result["is_free"] is False and result["free_shipping_reason"] is None
    assert result["estimated_days"] == "1-2 days"


def test_inside_dhaka_costs_70_and_everywhere_else_120(seeded):
    assert quote("Dhaka")["charge"] == D("70.00")
    assert quote("Rajshahi")["charge"] == D("120.00")
    assert quote("Nowhere")["charge"] == D("120.00")


def test_a_delivery_method_adds_its_extra_on_top(seeded):
    DeliveryMethod.objects.filter(slug="express").update(is_active=True)
    cache.clear()
    result = quote("Dhaka", method="express")
    assert result["charge"] == D("170.00") and result["zone_charge"] == D("70.00")
    assert result["delivery_method"]["slug"] == "express"
    assert result["estimated_days"] == "Next day"  # the method's own estimate wins


def test_the_standard_method_adds_nothing(seeded):
    assert quote("Dhaka", method="standard")["charge"] == D("70.00")


def test_an_inactive_or_unknown_method_is_refused(seeded):
    for slug in ("express", "teleport"):  # express is seeded inactive
        with pytest.raises(ValidationError) as exc:
            quote("Dhaka", method=slug)
        assert "delivery_method" in exc.value.message_dict


def test_no_method_means_no_extra_even_when_methods_exist(seeded):
    assert quote("Dhaka")["charge"] == D("70.00") and quote("Dhaka")["delivery_method"] is None


def test_reaching_the_global_threshold_makes_delivery_free(seeded):
    set_global_threshold("2000.00")
    assert quote("Dhaka", "1999.99")["is_free"] is False
    at = quote("Dhaka", "2000.00")  # the boundary itself qualifies
    assert at["is_free"] and at["charge"] == D("0.00") and at["free_shipping_reason"] == "free_shipping_threshold"
    assert quote("Sylhet", "5000")["charge"] == D("0.00")


def test_no_global_threshold_means_never_free_by_amount(seeded):
    for blank in (None, D("0")):
        set_global_threshold(blank)
        cache.clear()
        assert quote("Dhaka", "1000000")["is_free"] is False


def test_a_zone_override_beats_the_global_threshold(seeded):
    set_global_threshold("2000.00")
    DeliveryZone.objects.filter(slug="inside-dhaka").update(free_shipping_threshold="500.00")
    cache.clear()
    assert quote("Dhaka", "500")["is_free"] is True  # its own, lower threshold
    assert quote("Sylhet", "500")["is_free"] is False  # the other zone still uses the global one
    assert quote("Sylhet", "2000")["is_free"] is True


def test_an_override_of_zero_means_never_free_even_with_a_global_threshold(seeded):
    set_global_threshold("100.00")
    DeliveryZone.objects.filter(slug="inside-dhaka").update(free_shipping_threshold="0.00")
    cache.clear()
    assert quote("Dhaka", "999999")["is_free"] is False and quote("Dhaka", "999999")["charge"] == D("70.00")


def test_a_blank_override_uses_the_global_threshold(seeded):
    set_global_threshold("300.00")
    assert quote("Dhaka", "300")["is_free"] is True


def test_a_zone_override_still_works_when_there_is_no_global_threshold(seeded):
    set_global_threshold(None)
    DeliveryZone.objects.filter(slug="inside-dhaka").update(free_shipping_threshold="800.00")
    cache.clear()
    assert quote("Dhaka", "800")["is_free"] is True


def test_a_free_shipping_coupon_makes_delivery_free(seeded):
    coupon = SimpleNamespace(free_shipping=True)
    result = quote("Dhaka", "100", coupon)
    assert result["is_free"] and result["charge"] == D("0.00") and result["free_shipping_reason"] == "coupon_free_shipping"


def test_a_coupon_without_free_shipping_changes_nothing(seeded):
    assert quote("Dhaka", "100", SimpleNamespace(free_shipping=False))["charge"] == D("70.00")
    assert quote("Dhaka", "100", None)["charge"] == D("70.00")


def test_when_both_apply_the_threshold_is_the_reported_reason(seeded):
    set_global_threshold("100.00")
    assert quote("Dhaka", "100", SimpleNamespace(free_shipping=True))["free_shipping_reason"] == "free_shipping_threshold"


def test_free_shipping_waives_the_method_extra_too(seeded):
    DeliveryMethod.objects.filter(slug="express").update(is_active=True)
    cache.clear()
    assert quote("Dhaka", "100", SimpleNamespace(free_shipping=True), method="express")["charge"] == D("0.00")


def test_the_threshold_reported_is_the_effective_one(seeded):
    set_global_threshold("2000.00")
    assert quote("Dhaka")["free_shipping_threshold"] == D("2000.00")
    set_global_threshold(None)
    assert quote("Dhaka")["free_shipping_threshold"] is None


def test_the_address_can_be_an_object_or_a_dict(seeded):
    obj = SimpleNamespace(district="Dhaka", area="")
    assert services.calculate_shipping(obj, D("10")).get("charge") == D("70.00")
    assert services.calculate_shipping({"district": "Dhaka"}, D("10"))["charge"] == D("70.00")


@pytest.mark.parametrize("bad", ["lots", "NaN", "Infinity", "-5", None])
def test_the_subtotal_must_be_a_non_negative_number(seeded, bad):
    with pytest.raises(ValidationError) as exc:
        services.calculate_shipping({"district": "Dhaka"}, bad)
    assert "subtotal" in exc.value.message_dict


# --- a change takes effect immediately; old quotes are snapshots ---------------------------------------------


def test_a_new_charge_is_used_by_the_very_next_calculation(seeded):
    assert quote("Dhaka")["charge"] == D("70.00")  # primes the cache
    services.change_charge(seeded["inside-dhaka"], "85.00")
    assert quote("Dhaka")["charge"] == D("85.00")


def test_any_edit_path_refreshes_the_cache_not_just_the_service(seeded):
    assert quote("Dhaka")["charge"] == D("70.00")
    zone = DeliveryZone.objects.get(slug="inside-dhaka")
    zone.charge = D("77.00")
    zone.save()  # a plain ORM save (the Django admin, a shell), no service involved
    assert quote("Dhaka")["charge"] == D("77.00")


def test_coverage_changes_also_refresh_the_cache(seeded):
    assert quote("Sylhet")["zone_name"] == "Outside Dhaka"
    ZoneDistrict.objects.create(zone=seeded["inside-dhaka"], district=district("Sylhet"), areas=[])
    assert quote("Sylhet")["zone_name"] == "Inside Dhaka"


def test_method_changes_also_refresh_the_cache(seeded):
    with pytest.raises(ValidationError):
        quote("Dhaka", method="express")
    DeliveryMethod.objects.filter(slug="express").first().save()  # unchanged (inactive)
    method = DeliveryMethod.objects.get(slug="express")
    method.is_active = True
    method.save()
    assert quote("Dhaka", method="express")["charge"] == D("170.00")


def test_a_quote_is_a_plain_snapshot_that_a_later_charge_change_cannot_touch(seeded):
    """What checkout stores on an order is this dict's values; nothing in it points back at the zone's row."""
    stored = quote("Dhaka")
    services.change_charge(seeded["inside-dhaka"], "999.00")
    assert stored["charge"] == D("70.00") and quote("Dhaka")["charge"] == D("999.00")
    assert not any(isinstance(v, DeliveryZone) for v in stored.values())


def test_a_cache_outage_falls_back_to_the_database(seeded):
    with mock.patch.object(cache, "get", side_effect=ConnectionError("redis down")), \
         mock.patch.object(cache, "set", side_effect=ConnectionError("redis down")):
        assert quote("Dhaka")["charge"] == D("70.00")
        services.change_charge(seeded["inside-dhaka"], "80.00")  # invalidation failing must not break the save
    assert DeliveryZone.objects.get(slug="inside-dhaka").charge == D("80.00")


def test_the_index_is_served_from_cache_on_repeat_calls(seeded, django_assert_num_queries):
    services.get_index()
    with django_assert_num_queries(0):
        services.get_index()


# --- changing a charge ------------------------------------------------------------------------------------------


def test_change_charge_writes_history_with_who_changed_it(seeded, admin_user):
    zone = services.change_charge(seeded["inside-dhaka"], "85.50", user=admin_user)
    assert zone.charge == D("85.50")
    row = ShippingChargeHistory.objects.filter(zone=zone).first()
    assert (row.old_charge, row.new_charge, row.changed_by, row.zone_name) == (D("70.00"), D("85.50"), admin_user, "Inside Dhaka")


def test_setting_the_same_charge_writes_no_history(seeded):
    before = ShippingChargeHistory.objects.count()
    services.change_charge(seeded["inside-dhaka"], "70.00")
    assert ShippingChargeHistory.objects.count() == before


@pytest.mark.parametrize(("value", "code"), [
    ("-1", "negative_charge"), ("5000.01", "charge_too_high"), ("abc", "invalid"), (None, "invalid"), ("NaN", "invalid"),
    ("Infinity", "invalid"), ("-Infinity", "invalid"),
])
def test_bad_charges_are_refused_and_change_nothing(seeded, value, code):
    with pytest.raises(ValidationError) as exc:
        services.change_charge(seeded["inside-dhaka"], value)
    assert exc.value.error_dict["charge"][0].code == code
    assert DeliveryZone.objects.get(slug="inside-dhaka").charge == D("70.00")


def test_the_maximum_charge_is_allowed_and_zero_is_allowed(seeded):
    assert services.change_charge(seeded["inside-dhaka"], "5000.00").charge == D("5000.00")
    assert services.change_charge(seeded["inside-dhaka"], "0").charge == D("0.00")


def test_the_maximum_comes_from_settings(seeded, settings):
    settings.SHIPPING_MAX_CHARGE = "300.00"
    with pytest.raises(ValidationError):
        services.change_charge(seeded["inside-dhaka"], "300.01")
    assert services.change_charge(seeded["inside-dhaka"], "300.00").charge == D("300.00")


# --- default-zone rules ------------------------------------------------------------------------------------------


def edit(zone, **fields):
    zone = DeliveryZone.objects.get(pk=zone.pk)
    for name, value in fields.items():
        setattr(zone, name, value)
    return services.save_zone(zone)


def test_the_default_zone_cannot_be_unset(seeded):
    with pytest.raises(ValidationError) as exc:
        edit(seeded["outside-dhaka"], is_default=False)
    assert exc.value.error_dict["is_default"][0].code == "default_zone_required"
    assert DeliveryZone.objects.get(is_default=True) == seeded["outside-dhaka"]


def test_the_default_zone_cannot_be_deactivated(seeded):
    with pytest.raises(ValidationError) as exc:
        edit(seeded["outside-dhaka"], is_active=False)
    assert exc.value.error_dict["is_active"][0].code == "default_zone_inactive"


def test_making_another_zone_the_default_swaps_it_atomically(seeded):
    edit(seeded["inside-dhaka"], is_default=True)
    assert list(DeliveryZone.objects.filter(is_default=True)) == [seeded["inside-dhaka"]]
    assert DeliveryZone.objects.get(pk=seeded["outside-dhaka"].pk).is_default is False


def test_an_inactive_zone_cannot_become_the_default(seeded):
    spare = DeliveryZoneFactory(is_active=False)
    with pytest.raises(ValidationError):
        edit(spare, is_default=True)
    assert DeliveryZone.objects.get(is_default=True) == seeded["outside-dhaka"]


def test_a_new_zone_can_be_created_as_the_default_and_takes_over(seeded):
    zone = DeliveryZone(name="Everywhere", slug="everywhere", charge=D("150"), is_default=True)
    services.save_zone(zone)
    assert list(DeliveryZone.objects.filter(is_default=True)) == [zone]


def test_creating_a_zone_logs_its_initial_charge(seeded, admin_user):
    zone = services.save_zone(DeliveryZone(name="Sylhet Metro", slug="sylhet-metro", charge=D("90")), user=admin_user)
    row = ShippingChargeHistory.objects.get(zone=zone)
    assert (row.old_charge, row.new_charge, row.changed_by) == (None, D("90.00"), admin_user)


def test_editing_a_charge_through_save_zone_is_logged_too(seeded):
    edit(seeded["inside-dhaka"], charge=D("65.00"))
    row = ShippingChargeHistory.objects.filter(zone=seeded["inside-dhaka"]).first()
    assert (row.old_charge, row.new_charge) == (D("70.00"), D("65.00"))


def test_saving_without_a_charge_change_writes_no_history(seeded):
    before = ShippingChargeHistory.objects.count()
    edit(seeded["inside-dhaka"], sort_order=9)
    assert ShippingChargeHistory.objects.count() == before


# --- deleting -----------------------------------------------------------------------------------------------------


def test_the_default_zone_cannot_be_deleted(seeded):
    from apps.catalog.exceptions import Conflict
    with pytest.raises(Conflict) as exc:
        services.delete_zone(seeded["outside-dhaka"])
    assert exc.value.get_codes() == "default_zone" and DeliveryZone.objects.filter(pk=seeded["outside-dhaka"].pk).exists()


def test_a_zone_with_orders_cannot_be_deleted(seeded, monkeypatch):
    from apps.catalog.exceptions import Conflict
    monkeypatch.setattr(DeliveryZone, "orders", SimpleNamespace(exists=lambda: True), raising=False)
    with pytest.raises(Conflict) as exc:
        services.delete_zone(seeded["inside-dhaka"])
    assert exc.value.get_codes() == "zone_in_use" and DeliveryZone.objects.filter(pk=seeded["inside-dhaka"].pk).exists()


def test_an_unused_zone_is_deleted_and_its_coverage_goes_with_it(seeded):
    spare = cover(DeliveryZoneFactory(), "Sylhet")
    services.delete_zone(spare)
    assert not DeliveryZone.objects.filter(pk=spare.pk).exists()
    assert not ZoneDistrict.objects.filter(district=district("Sylhet")).exists()
    assert quote("Sylhet")["zone_name"] == "Outside Dhaka"


def test_has_orders_is_false_while_no_orders_exist(seeded):
    assert services.has_orders(seeded["inside-dhaka"]) is False


# --- coverage validation -------------------------------------------------------------------------------------------


def zone_with(coverage, **kw):
    zone = DeliveryZoneFactory(**kw)
    return services.save_zone(zone, coverage=coverage)


def test_coverage_is_replaced_not_merged():
    zone = zone_with([{"district_id": district("Sylhet").id, "areas": []}])
    services.save_zone(zone, coverage=[{"district_id": district("Khulna").id, "areas": []}])
    assert list(zone.coverage.values_list("district__name", flat=True)) == ["Khulna"]


def test_coverage_none_leaves_districts_alone_and_empty_clears_them():
    zone = zone_with([{"district_id": district("Sylhet").id, "areas": []}])
    services.save_zone(zone, coverage=None)
    assert zone.coverage.count() == 1
    services.save_zone(zone, coverage=[])
    assert zone.coverage.count() == 0


def test_a_district_listed_twice_is_refused():
    sylhet = district("Sylhet").id
    with pytest.raises(ValidationError) as exc:
        zone_with([{"district_id": sylhet, "areas": []}, {"district_id": sylhet, "areas": ["Zindabazar"]}])
    assert exc.value.error_dict["coverage"][0].code == "duplicate_district"


def test_an_unknown_district_is_refused():
    with pytest.raises(ValidationError) as exc:
        zone_with([{"district_id": 999999, "areas": []}])
    assert exc.value.error_dict["coverage"][0].code == "unknown_district"


def test_a_district_already_owned_by_another_zone_is_refused_with_its_name():
    cover(DeliveryZoneFactory(name="Sylhet Team"), "Sylhet")
    with pytest.raises(ValidationError) as exc:
        zone_with([{"district_id": district("Sylhet").id, "areas": []}])
    error = exc.value.error_dict["coverage"][0]
    assert error.code == "district_already_assigned" and "Sylhet Team" in error.message


def test_two_zones_cannot_claim_the_same_area():
    cover(DeliveryZoneFactory(), "Dhaka", areas=["Mirpur"])
    with pytest.raises(ValidationError) as exc:
        zone_with([{"district_id": district("Dhaka").id, "areas": ["mirpur ", "Savar"]}])
    assert exc.value.error_dict["coverage"][0].code == "area_already_assigned"


def test_area_rules_may_sit_beside_a_whole_district_zone_either_way_round():
    cover(DeliveryZoneFactory(), "Dhaka")
    zone_with([{"district_id": district("Dhaka").id, "areas": ["Mirpur"]}])  # partial beside whole: fine
    other = DeliveryZoneFactory()
    services.save_zone(other, coverage=[{"district_id": district("Rajshahi").id, "areas": ["Boalia"]}])
    zone_with([{"district_id": district("Rajshahi").id, "areas": []}])  # whole beside partial: fine


def test_a_zone_can_be_resaved_with_its_own_coverage():
    zone = zone_with([{"district_id": district("Sylhet").id, "areas": []}])
    services.save_zone(zone, coverage=[{"district_id": district("Sylhet").id, "areas": []}])  # not a clash with itself
    assert zone.coverage.count() == 1


def test_areas_are_trimmed_and_deduplicated():
    zone = zone_with([{"district_id": district("Dhaka").id, "areas": [" Mirpur ", "Mirpur", "", "Savar"]}])
    assert zone.coverage.get().areas == ["Mirpur", "Savar"]
