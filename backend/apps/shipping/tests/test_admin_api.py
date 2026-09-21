from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.shipping.models import DeliveryMethod, DeliveryZone, ShippingChargeHistory, ZoneDistrict

from .factories import DeliveryMethodFactory, DeliveryZoneFactory, cover, district

pytestmark = pytest.mark.django_db

ZONES = "/api/v1/admin/shipping/zones/"
METHODS = "/api/v1/admin/shipping/methods/"
CALC = "/api/v1/shipping/calculate/"


def details(response):
    return response.json()["error"]["details"]


def code(response):
    return response.json()["error"]["code"]


def zone_url(zone, suffix=""):
    return f"{ZONES}{zone.id}/{suffix}"


# --- access control: Admin only ---------------------------------------------------------------------------------


@pytest.fixture
def every_route(seeded):
    zone, method = seeded["inside-dhaka"], DeliveryMethodFactory()
    return [
        ("get", ZONES), ("post", ZONES), ("get", zone_url(zone)), ("patch", zone_url(zone)), ("delete", zone_url(zone)),
        ("patch", zone_url(zone, "charge/")), ("get", zone_url(zone, "history/")),
        ("get", METHODS), ("post", METHODS), ("get", f"{METHODS}{method.id}/"), ("patch", f"{METHODS}{method.id}/"),
        ("delete", f"{METHODS}{method.id}/"),
    ]


def test_anonymous_gets_401_on_every_admin_shipping_route(api_client, every_route):
    for verb, url in every_route:
        assert getattr(api_client, verb)(url, {}, format="json").status_code == 401, (verb, url)


def test_customer_gets_403_on_every_admin_shipping_route(auth_client, customer, every_route):
    client = auth_client(customer)
    for verb, url in every_route:
        assert getattr(client, verb)(url, {}, format="json").status_code == 403, (verb, url)


def test_cce_gets_403_on_every_admin_shipping_route(auth_client, cce_user, every_route):
    client = auth_client(cce_user)
    for verb, url in every_route:
        assert getattr(client, verb)(url, {}, format="json").status_code == 403, (verb, url)


def test_a_forbidden_charge_change_changes_nothing(auth_client, cce_user, seeded):
    auth_client(cce_user).patch(zone_url(seeded["inside-dhaka"], "charge/"), {"charge": "1"}, format="json")
    assert DeliveryZone.objects.get(slug="inside-dhaka").charge == Decimal("70.00")


# --- list / retrieve --------------------------------------------------------------------------------------------


def test_list_includes_inactive_zones_and_is_paginated(admin_client, seeded):
    DeliveryZoneFactory(name="Off", is_active=False)
    body = admin_client.get(ZONES).json()
    assert body["count"] == 3 and {z["name"] for z in body["results"]} == {"Inside Dhaka", "Outside Dhaka", "Off"}


def test_the_zone_shape(admin_client, seeded):
    body = admin_client.get(zone_url(seeded["inside-dhaka"])).json()
    assert set(body) == {
        "id", "name", "slug", "description", "charge", "estimated_days_min", "estimated_days_max", "estimated_days_label",
        "estimated_days", "free_shipping_threshold", "is_active", "sort_order", "is_default", "coverage",
        "covers_all_other_districts", "created_at", "updated_at",
    }
    assert body["charge"] == "70.00" and body["estimated_days"] == "1-2 days"
    assert body["coverage"] == [{"district_id": district("Dhaka").id, "areas": [], "district_name": "Dhaka"}]
    assert body["covers_all_other_districts"] is False
    assert admin_client.get(zone_url(seeded["outside-dhaka"])).json()["covers_all_other_districts"] is True


def test_filter_search_and_ordering(admin_client, seeded):
    DeliveryZoneFactory(name="Sylhet Metro", is_active=False, charge="200.00")
    assert admin_client.get(f"{ZONES}?is_active=false").json()["count"] == 1
    assert admin_client.get(f"{ZONES}?is_default=true").json()["count"] == 1
    assert [z["name"] for z in admin_client.get(f"{ZONES}?search=metro").json()["results"]] == ["Sylhet Metro"]
    assert admin_client.get(f"{ZONES}?ordering=-charge").json()["results"][0]["name"] == "Sylhet Metro"


def test_retrieve_404_and_put_not_supported(admin_client, seeded):
    assert admin_client.get(f"{ZONES}99999/").status_code == 404
    assert admin_client.put(zone_url(seeded["inside-dhaka"]), {}, format="json").status_code == 405


# --- create ------------------------------------------------------------------------------------------------------


def test_create_a_zone_with_everything(admin_client, seeded):
    sylhet, khulna = district("Sylhet"), district("Khulna")
    r = admin_client.post(ZONES, {
        "name": "Sylhet Region", "charge": "150.00", "estimated_days_min": 2, "estimated_days_max": 4,
        "free_shipping_threshold": "3000.00", "is_active": True, "sort_order": 5,
        "coverage": [{"district_id": sylhet.id}, {"district_id": khulna.id, "areas": ["Sonadanga"]}],
    }, format="json")
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body["slug"] == "sylhet-region" and body["charge"] == "150.00" and body["is_default"] is False
    assert body["estimated_days"] == "2-4 days" and body["free_shipping_threshold"] == "3000.00"
    assert {(c["district_name"], tuple(c["areas"])) for c in body["coverage"]} == {("Sylhet", ()), ("Khulna", ("Sonadanga",))}


def test_creating_logs_the_initial_charge_against_the_admin(admin_client, admin_user, seeded):
    zone_id = admin_client.post(ZONES, {"name": "New", "charge": "88"}, format="json").json()["id"]
    row = ShippingChargeHistory.objects.get(zone_id=zone_id)
    assert (row.old_charge, row.new_charge, row.changed_by) == (None, Decimal("88.00"), admin_user)


def test_the_minimum_payload_is_a_name_and_a_charge(admin_client, seeded):
    r = admin_client.post(ZONES, {"name": "Tiny", "charge": "0"}, format="json")
    assert r.status_code == 201 and r.json()["charge"] == "0.00" and r.json()["is_active"] is True


def test_name_and_charge_are_required(admin_client, seeded):
    r = admin_client.post(ZONES, {}, format="json")
    assert r.status_code == 400 and {"name", "charge"} <= set(details(r))


def test_a_custom_slug_is_kept_and_a_duplicate_slug_is_refused(admin_client, seeded):
    assert admin_client.post(ZONES, {"name": "A", "slug": "my-slug", "charge": "1"}, format="json").json()["slug"] == "my-slug"
    r = admin_client.post(ZONES, {"name": "B", "slug": "my-slug", "charge": "1"}, format="json")
    assert r.status_code == 400


def test_zone_names_are_unique_ignoring_case(admin_client, seeded):
    r = admin_client.post(ZONES, {"name": "inside dhaka", "charge": "1"}, format="json")
    assert r.status_code == 400 and "non_field_errors" in details(r)


@pytest.mark.parametrize(("value", "err"), [
    ("-1", "negative_charge"), ("5000.01", "charge_too_high"), ("99999999", "charge_too_high"),
])
def test_charge_validation_on_create(admin_client, seeded, value, err):
    r = admin_client.post(ZONES, {"name": "X", "charge": value}, format="json")
    assert r.status_code == 400 and "charge" in details(r)


@pytest.mark.parametrize("value", ["abc", "NaN", "Infinity", "", None, "1.234", "12345678901"])
def test_unparseable_charges_are_400s_not_500s(admin_client, seeded, value):
    r = admin_client.post(ZONES, {"name": "X", "charge": value}, format="json")
    assert r.status_code == 400 and "charge" in details(r)


def test_estimate_range_must_be_ordered(admin_client, seeded):
    r = admin_client.post(ZONES, {"name": "X", "charge": "1", "estimated_days_min": 5, "estimated_days_max": 2}, format="json")
    assert r.status_code == 400 and "estimated_days_max" in details(r)


def test_a_negative_threshold_is_refused_but_zero_and_blank_are_fine(admin_client, seeded):
    assert admin_client.post(ZONES, {"name": "N", "charge": "1", "free_shipping_threshold": "-1"}, format="json").status_code == 400
    zero = admin_client.post(ZONES, {"name": "Z", "charge": "1", "free_shipping_threshold": "0"}, format="json")
    blank = admin_client.post(ZONES, {"name": "B", "charge": "1", "free_shipping_threshold": None}, format="json")
    assert zero.json()["free_shipping_threshold"] == "0.00" and blank.json()["free_shipping_threshold"] is None


# --- update -------------------------------------------------------------------------------------------------------


def test_patch_updates_any_field_and_only_the_fields_sent(admin_client, seeded):
    zone = seeded["inside-dhaka"]
    r = admin_client.patch(zone_url(zone), {"charge": "75.00", "estimated_days_label": "Same day", "sort_order": 7}, format="json")
    assert r.status_code == 200
    body = r.json()
    assert body["charge"] == "75.00" and body["estimated_days"] == "Same day" and body["sort_order"] == 7
    assert body["name"] == "Inside Dhaka" and body["is_active"] is True
    assert len(body["coverage"]) == 1  # coverage not sent, not touched


def test_renaming_regenerates_an_automatic_slug(admin_client, seeded):
    zone = seeded["inside-dhaka"]
    assert admin_client.patch(zone_url(zone), {"name": "Dhaka City"}, format="json").json()["slug"] == "dhaka-city"


def test_deactivating_a_non_default_zone_works_and_it_disappears_from_the_storefront(admin_client, api_client, seeded):
    admin_client.patch(zone_url(seeded["inside-dhaka"]), {"is_active": False}, format="json")
    assert [z["name"] for z in api_client.get("/api/v1/shipping/zones/").json()] == ["Outside Dhaka"]
    assert api_client.post(CALC, {"district": "Dhaka", "subtotal": "10"}, format="json").json()["charge"] == "120.00"


def test_patching_the_charge_negative_or_too_big_is_refused_and_changes_nothing(admin_client, seeded):
    zone = seeded["inside-dhaka"]
    for bad in ("-5", "6000"):
        assert admin_client.patch(zone_url(zone), {"charge": bad}, format="json").status_code == 400
    assert DeliveryZone.objects.get(pk=zone.pk).charge == Decimal("70.00")


# --- the quick "change delivery fee" endpoint -----------------------------------------------------------------------


def test_charge_endpoint_updates_only_the_charge(admin_client, seeded):
    zone = seeded["inside-dhaka"]
    r = admin_client.patch(zone_url(zone, "charge/"), {"charge": "82.50"}, format="json")
    assert r.status_code == 200
    body = r.json()
    assert body["charge"] == "82.50" and body["id"] == zone.id and body["name"] == "Inside Dhaka"
    fresh = DeliveryZone.objects.get(pk=zone.pk)
    assert fresh.charge == Decimal("82.50") and fresh.is_active and fresh.estimated_days_min == 1


def test_charge_endpoint_ignores_other_fields(admin_client, seeded):
    zone = seeded["inside-dhaka"]
    admin_client.patch(zone_url(zone, "charge/"), {"charge": "80", "name": "Hacked", "is_active": False, "is_default": True}, format="json")
    fresh = DeliveryZone.objects.get(pk=zone.pk)
    assert (fresh.name, fresh.is_active, fresh.is_default) == ("Inside Dhaka", True, False)


def test_charge_endpoint_requires_a_valid_charge(admin_client, seeded):
    zone = seeded["inside-dhaka"]
    for payload in ({}, {"charge": ""}, {"charge": "abc"}, {"charge": "-1"}, {"charge": "5001"}, {"charge": "NaN"}):
        r = admin_client.patch(zone_url(zone, "charge/"), payload, format="json")
        assert r.status_code == 400 and "charge" in details(r), payload
    assert DeliveryZone.objects.get(pk=zone.pk).charge == Decimal("70.00")


def test_charge_endpoint_404_and_put_not_supported(admin_client, seeded):
    assert admin_client.patch(f"{ZONES}99999/charge/", {"charge": "1"}, format="json").status_code == 404
    assert admin_client.put(zone_url(seeded["inside-dhaka"], "charge/"), {"charge": "1"}, format="json").status_code == 405


def test_charge_change_is_visible_to_the_calculator_at_once(admin_client, api_client, seeded):
    calc = lambda: api_client.post(CALC, {"district": "Dhaka", "subtotal": "10"}, format="json").json()["charge"]  # noqa: E731
    assert calc() == "70.00"
    admin_client.patch(zone_url(seeded["inside-dhaka"], "charge/"), {"charge": "55"}, format="json")
    assert calc() == "55.00"


# --- history ------------------------------------------------------------------------------------------------------------


def test_every_charge_change_lands_in_the_history_newest_first(admin_client, admin_user, seeded):
    zone = seeded["inside-dhaka"]
    admin_client.patch(zone_url(zone, "charge/"), {"charge": "80"}, format="json")
    admin_client.patch(zone_url(zone), {"charge": "90"}, format="json")  # the full edit logs too
    body = admin_client.get(zone_url(zone, "history/")).json()
    assert body["count"] == 3
    assert [(r["old_charge"], r["new_charge"]) for r in body["results"]] == [("80.00", "90.00"), ("70.00", "80.00"), (None, "70.00")]
    top = body["results"][0]
    assert top["changed_by"] == {"id": admin_user.id, "full_name": admin_user.full_name}
    assert set(top) == {"id", "zone", "zone_name", "old_charge", "new_charge", "changed_by", "created_at"}


def test_history_is_per_zone(admin_client, seeded):
    admin_client.patch(zone_url(seeded["inside-dhaka"], "charge/"), {"charge": "80"}, format="json")
    assert admin_client.get(zone_url(seeded["outside-dhaka"], "history/")).json()["count"] == 1  # only its initial entry


def test_an_unchanged_charge_adds_no_history(admin_client, seeded):
    zone = seeded["inside-dhaka"]
    admin_client.patch(zone_url(zone, "charge/"), {"charge": "70.00"}, format="json")
    admin_client.patch(zone_url(zone), {"sort_order": 4}, format="json")
    assert admin_client.get(zone_url(zone, "history/")).json()["count"] == 1


def test_history_404_for_an_unknown_zone(admin_client, seeded):
    assert admin_client.get(f"{ZONES}99999/history/").status_code == 404


def test_history_is_read_only(admin_client, seeded):
    assert admin_client.post(zone_url(seeded["inside-dhaka"], "history/"), {}, format="json").status_code == 405


def test_history_survives_the_zone_being_deleted(admin_client, seeded):
    zone = DeliveryZoneFactory(name="Short lived", charge="10.00")
    admin_client.patch(zone_url(zone, "charge/"), {"charge": "20"}, format="json")
    assert admin_client.delete(zone_url(zone)).status_code == 204
    rows = ShippingChargeHistory.objects.filter(zone_name="Short lived")
    assert rows.count() == 1 and rows.get().zone is None


# --- the default-zone rules ------------------------------------------------------------------------------------------------


def test_the_default_zone_cannot_be_deleted(admin_client, seeded):
    r = admin_client.delete(zone_url(seeded["outside-dhaka"]))
    assert r.status_code == 409 and code(r) == "default_zone"
    assert DeliveryZone.objects.filter(is_default=True).count() == 1


def test_the_default_zone_cannot_be_deactivated(admin_client, seeded):
    r = admin_client.patch(zone_url(seeded["outside-dhaka"]), {"is_active": False}, format="json")
    assert r.status_code == 400 and "is_active" in details(r)
    assert DeliveryZone.objects.get(slug="outside-dhaka").is_active


def test_the_default_flag_cannot_simply_be_removed(admin_client, seeded):
    r = admin_client.patch(zone_url(seeded["outside-dhaka"]), {"is_default": False}, format="json")
    assert r.status_code == 400 and "is_default" in details(r)
    assert DeliveryZone.objects.get(is_default=True).slug == "outside-dhaka"


def test_marking_another_zone_default_moves_the_flag(admin_client, seeded):
    r = admin_client.patch(zone_url(seeded["inside-dhaka"]), {"is_default": True}, format="json")
    assert r.status_code == 200 and r.json()["is_default"] is True
    assert list(DeliveryZone.objects.filter(is_default=True).values_list("slug", flat=True)) == ["inside-dhaka"]
    # ...and the old default can now be deactivated or deleted like any other zone
    assert admin_client.patch(zone_url(seeded["outside-dhaka"]), {"is_active": False}, format="json").status_code == 200
    assert admin_client.delete(zone_url(seeded["outside-dhaka"])).status_code == 204


def test_an_inactive_zone_cannot_be_made_the_default(admin_client, seeded):
    spare = DeliveryZoneFactory(is_active=False)
    r = admin_client.patch(zone_url(spare), {"is_default": True}, format="json")
    assert r.status_code == 400 and DeliveryZone.objects.get(is_default=True).slug == "outside-dhaka"


def test_creating_a_zone_as_default_takes_over_atomically(admin_client, seeded):
    r = admin_client.post(ZONES, {"name": "Everywhere", "charge": "140", "is_default": True}, format="json")
    assert r.status_code == 201 and DeliveryZone.objects.filter(is_default=True).count() == 1
    assert DeliveryZone.objects.get(is_default=True).name == "Everywhere"


def test_creating_an_inactive_default_is_refused(admin_client, seeded):
    r = admin_client.post(ZONES, {"name": "Off", "charge": "1", "is_default": True, "is_active": False}, format="json")
    assert r.status_code == 400 and DeliveryZone.objects.get(is_default=True).slug == "outside-dhaka"


def test_there_is_always_exactly_one_active_default_after_every_kind_of_edit(admin_client, seeded):
    other = DeliveryZoneFactory(name="Other")
    attempts = [
        ("patch", zone_url(seeded["outside-dhaka"]), {"is_default": False}),
        ("patch", zone_url(seeded["outside-dhaka"]), {"is_active": False}),
        ("delete", zone_url(seeded["outside-dhaka"]), None),
        ("patch", zone_url(other), {"is_default": True, "is_active": False}),
        ("patch", zone_url(other), {"is_default": True}),
        ("delete", zone_url(other), None),
        ("delete", zone_url(seeded["outside-dhaka"]), None),
    ]
    for verb, url, payload in attempts:
        getattr(admin_client, verb)(url, payload, format="json")
        defaults = DeliveryZone.objects.filter(is_default=True)
        assert defaults.count() == 1 and defaults.get().is_active, (verb, url, payload)


# --- deleting -------------------------------------------------------------------------------------------------------------------


def test_delete_an_unused_zone(admin_client, seeded):
    zone = cover(DeliveryZoneFactory(), "Sylhet")
    assert admin_client.delete(zone_url(zone)).status_code == 204
    assert not DeliveryZone.objects.filter(pk=zone.pk).exists() and not ZoneDistrict.objects.filter(district=district("Sylhet")).exists()


def test_a_zone_with_orders_cannot_be_deleted_only_deactivated(admin_client, seeded, monkeypatch):
    zone = DeliveryZoneFactory()
    monkeypatch.setattr(DeliveryZone, "orders", SimpleNamespace(exists=lambda: True), raising=False)
    r = admin_client.delete(zone_url(zone))
    assert r.status_code == 409 and code(r) == "zone_in_use" and "Deactivate" in r.json()["error"]["message"]
    assert DeliveryZone.objects.filter(pk=zone.pk).exists()
    assert admin_client.patch(zone_url(zone), {"is_active": False}, format="json").status_code == 200


# --- coverage through the API ---------------------------------------------------------------------------------------------------------


def test_coverage_replace_clear_and_omit(admin_client, seeded):
    zone = DeliveryZoneFactory()
    sylhet, khulna = district("Sylhet").id, district("Khulna").id
    admin_client.patch(zone_url(zone), {"coverage": [{"district_id": sylhet}]}, format="json")
    assert [c["district_id"] for c in admin_client.get(zone_url(zone)).json()["coverage"]] == [sylhet]
    admin_client.patch(zone_url(zone), {"coverage": [{"district_id": khulna, "areas": ["Sonadanga"]}]}, format="json")
    assert [(c["district_id"], c["areas"]) for c in admin_client.get(zone_url(zone)).json()["coverage"]] == [(khulna, ["Sonadanga"])]
    admin_client.patch(zone_url(zone), {"name": "Renamed"}, format="json")
    assert len(admin_client.get(zone_url(zone)).json()["coverage"]) == 1
    admin_client.patch(zone_url(zone), {"coverage": []}, format="json")
    assert admin_client.get(zone_url(zone)).json()["coverage"] == []


def test_coverage_errors_are_400s_naming_the_problem_and_change_nothing(admin_client, seeded):
    zone = DeliveryZoneFactory()
    sylhet = district("Sylhet").id
    cases = [
        ([{"district_id": district("Dhaka").id}], "already covered by the zone “Inside Dhaka”"),
        ([{"district_id": 999999}], "Unknown district"),
        ([{"district_id": sylhet}, {"district_id": sylhet}], "only once per zone"),
    ]
    for coverage, message in cases:
        r = admin_client.patch(zone_url(zone), {"coverage": coverage}, format="json")
        assert r.status_code == 400, coverage
        assert message in details(r)["coverage"][0], (coverage, details(r))
    assert zone.coverage.count() == 0


def test_malformed_coverage_is_a_400(admin_client, seeded):
    zone = DeliveryZoneFactory()
    for bad in ("Dhaka", [{"district": 1}], [{}], [{"district_id": "x"}], [{"district_id": 0}], [{"district_id": 5, "areas": "Mirpur"}]):
        assert admin_client.patch(zone_url(zone), {"coverage": bad}, format="json").status_code == 400, bad
        assert admin_client.post(ZONES, {"name": "Bad", "charge": "1", "coverage": bad}, format="json").status_code == 400, bad


def test_splitting_dhaka_into_city_and_outer_end_to_end(admin_client, api_client, seeded):
    """The spec's "Dhaka city vs outer Dhaka": free Dhaka from Inside Dhaka, then hand each part to a zone."""
    dhaka = district("Dhaka").id
    assert admin_client.patch(zone_url(seeded["inside-dhaka"]), {"coverage": []}, format="json").status_code == 200
    city = admin_client.post(ZONES, {"name": "Dhaka City", "charge": "60", "coverage": [{"district_id": dhaka, "areas": ["Mirpur", "Gulshan"]}]}, format="json")
    outer = admin_client.post(ZONES, {"name": "Outer Dhaka", "charge": "100", "coverage": [{"district_id": dhaka}]}, format="json")
    assert city.status_code == 201 and outer.status_code == 201
    quote = lambda area: api_client.post(CALC, {"district": "Dhaka", "area": area, "subtotal": "1"}, format="json").json()  # noqa: E731
    assert quote("Mirpur")["zone_name"] == "Dhaka City" and quote("Mirpur")["charge"] == "60.00"
    assert quote("Savar")["zone_name"] == "Outer Dhaka" and quote("Savar")["charge"] == "100.00"
    assert quote("")["zone_name"] == "Outer Dhaka"


# --- delivery methods --------------------------------------------------------------------------------------------------------------------


def test_method_crud(admin_client, seeded):
    r = admin_client.post(METHODS, {"name": "Same Day", "extra_charge": "200", "estimated_days_label": "Today"}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "same-day" and body["extra_charge"] == "200.00" and body["is_active"] is False  # off by default
    url = f"{METHODS}{body['id']}/"
    assert admin_client.patch(url, {"is_active": True, "extra_charge": "180"}, format="json").json()["extra_charge"] == "180.00"
    assert admin_client.get(url).status_code == 200 and admin_client.put(url, {}, format="json").status_code == 405
    assert admin_client.delete(url).status_code == 204


def test_method_list_includes_inactive_and_filters(admin_client, seeded):
    assert admin_client.get(METHODS).json()["count"] == 2
    assert [m["slug"] for m in admin_client.get(f"{METHODS}?is_active=false").json()["results"]] == ["express"]


def test_method_validation(admin_client, seeded):
    assert admin_client.post(METHODS, {"name": "standard", "extra_charge": "1"}, format="json").status_code == 400  # name taken (ci)
    for bad in ("-1", "5001", "abc", "NaN"):
        r = admin_client.post(METHODS, {"name": "X", "extra_charge": bad}, format="json")
        assert r.status_code == 400 and "extra_charge" in details(r), bad
    assert admin_client.post(METHODS, {"extra_charge": "1"}, format="json").status_code == 400


def test_enabling_a_method_makes_it_usable_immediately(admin_client, api_client, seeded):
    express = DeliveryMethod.objects.get(slug="express")
    body = {"district": "Dhaka", "subtotal": "10", "delivery_method": "express"}
    assert api_client.post(CALC, body, format="json").status_code == 400
    admin_client.patch(f"{METHODS}{express.id}/", {"is_active": True}, format="json")
    assert api_client.post(CALC, body, format="json").json()["charge"] == "170.00"
    admin_client.patch(f"{METHODS}{express.id}/", {"extra_charge": "40"}, format="json")
    assert api_client.post(CALC, body, format="json").json()["charge"] == "110.00"


def test_a_method_with_orders_cannot_be_deleted(admin_client, seeded, monkeypatch):
    method = DeliveryMethodFactory()
    monkeypatch.setattr(DeliveryMethod, "orders", SimpleNamespace(exists=lambda: True), raising=False)
    r = admin_client.delete(f"{METHODS}{method.id}/")
    assert r.status_code == 409 and code(r) == "method_in_use" and DeliveryMethod.objects.filter(pk=method.pk).exists()
