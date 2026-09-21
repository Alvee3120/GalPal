from decimal import Decimal

import pytest

from apps.catalog.tests.factories import ProductFactory
from apps.coupons.tests.factories import CouponFactory
from apps.shipping import services
from apps.shipping.models import DeliveryMethod, DeliveryZone
from apps.site_settings.models import SiteSettings

from .factories import DeliveryMethodFactory, DeliveryZoneFactory, cover

pytestmark = pytest.mark.django_db

ZONES = "/api/v1/shipping/zones/"
METHODS = "/api/v1/shipping/methods/"
DISTRICTS = "/api/v1/shipping/districts/"
CALC = "/api/v1/shipping/calculate/"
ITEMS = "/api/v1/cart/items/"
COUPON = "/api/v1/cart/coupon/"


def set_global_threshold(value):
    row, _ = SiteSettings.objects.get_or_create(id=1)
    row.free_shipping_threshold = value
    row.save()


def guest_cart(client, price="1000.00", quantity=1):
    product = ProductFactory(regular_price=price, stock_quantity=100)
    body = client.post(ITEMS, {"product_id": product.id, "quantity": quantity}, format="json").json()
    client.credentials(HTTP_X_CART_TOKEN=body["cart_token"])


# --- zones ------------------------------------------------------------------------------------------


def test_zones_are_public_and_list_the_seeded_defaults(api_client, seeded):
    r = api_client.get(ZONES)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)  # a short config list, deliberately not paginated
    assert [(z["name"], z["charge"]) for z in body] == [("Inside Dhaka", "70.00"), ("Outside Dhaka", "120.00")]
    assert set(body[0]) == {"id", "name", "slug", "charge", "estimated_days", "free_shipping_threshold", "is_default", "districts"}
    assert body[0]["estimated_days"] == "1-2 days" and body[0]["districts"] == ["Dhaka"]
    assert [z["is_default"] for z in body] == [False, True]


def test_inactive_zones_are_hidden_and_order_follows_sort_order(api_client, seeded):
    DeliveryZoneFactory(name="Hidden", is_active=False)
    DeliveryZoneFactory(name="First", sort_order=0, charge="10.00")
    names = [z["name"] for z in api_client.get(ZONES).json()]
    assert "Hidden" not in names and names[0] == "First"


def test_a_stale_or_garbage_token_does_not_break_the_public_lists(api_client, seeded):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    assert api_client.get(ZONES).status_code == 200 and api_client.get(DISTRICTS).status_code == 200


def test_zones_show_the_effective_free_shipping_threshold(api_client, seeded):
    set_global_threshold("2000.00")
    DeliveryZone.objects.filter(slug="inside-dhaka").update(free_shipping_threshold="500.00")
    by_name = {z["name"]: z["free_shipping_threshold"] for z in api_client.get(ZONES).json()}
    assert by_name == {"Inside Dhaka": "500.00", "Outside Dhaka": "2000.00"}
    set_global_threshold(None)
    assert {z["free_shipping_threshold"] for z in api_client.get(ZONES).json() if z["name"] == "Outside Dhaka"} == {None}


def test_a_changed_charge_shows_up_on_the_list_immediately(api_client, seeded, admin_client):
    api_client.get(ZONES)  # warm the cache
    r = admin_client.patch(f"/api/v1/admin/shipping/zones/{seeded['inside-dhaka'].id}/charge/", {"charge": "65.00"}, format="json")
    assert r.status_code == 200
    assert api_client.get(ZONES).json()[0]["charge"] == "65.00"


# --- methods / districts ---------------------------------------------------------------------------------


def test_only_active_methods_are_listed(api_client, seeded):
    body = api_client.get(METHODS).json()
    assert [m["slug"] for m in body] == ["standard"]  # express is seeded off
    assert set(body[0]) == {"id", "slug", "name", "description", "extra_charge", "estimated_days"}
    DeliveryMethod.objects.filter(slug="express").first().save()
    method = DeliveryMethod.objects.get(slug="express")
    method.is_active = True
    method.save()
    assert [m["slug"] for m in api_client.get(METHODS).json()] == ["standard", "express"]


def test_the_districts_list_has_all_64(api_client):
    body = api_client.get(DISTRICTS).json()
    assert len(body) == 64 and set(body[0]) == {"id", "name", "slug", "division"}
    assert {"Dhaka", "Sylhet", "Cox's Bazar"} <= {d["name"] for d in body}


# --- calculate ----------------------------------------------------------------------------------------------


def calc(client, **payload):
    return client.post(CALC, payload, format="json")


def test_inside_dhaka_is_70_and_outside_is_120(api_client, seeded):
    inside = calc(api_client, district="Dhaka", subtotal="500").json()
    assert inside["charge"] == "70.00" and inside["zone_name"] == "Inside Dhaka" and inside["is_free"] is False
    assert inside["free_shipping_reason"] is None and inside["estimated_days"] == "1-2 days"
    assert set(inside) == {"zone_id", "zone_name", "charge", "is_free", "free_shipping_reason", "estimated_days",
                           "zone_charge", "delivery_method", "free_shipping_threshold"}
    assert calc(api_client, district="Rajshahi", subtotal="500").json()["charge"] == "120.00"


def test_an_admin_charge_change_is_reflected_in_the_next_calculation(api_client, seeded, admin_client):
    assert calc(api_client, district="Dhaka", subtotal="10").json()["charge"] == "70.00"
    admin_client.patch(f"/api/v1/admin/shipping/zones/{seeded['inside-dhaka'].id}/charge/", {"charge": "90"}, format="json")
    assert calc(api_client, district="Dhaka", subtotal="10").json()["charge"] == "90.00"


def test_alias_and_case_variants_resolve(api_client, seeded):
    cover(DeliveryZoneFactory(name="Port", charge="99.00"), "Chattogram")
    assert calc(api_client, district="CHITTAGONG", subtotal="1").json()["charge"] == "99.00"


def test_area_selects_the_finer_zone(api_client, seeded):
    DeliveryZone.objects.filter(slug="inside-dhaka").first().coverage.all().delete()
    cover(DeliveryZoneFactory(name="Dhaka City", charge="60.00"), "Dhaka", areas=["Mirpur"])
    cover(DeliveryZoneFactory(name="Outer Dhaka", charge="95.00"), "Dhaka")
    assert calc(api_client, district="Dhaka", area="Mirpur", subtotal="1").json()["zone_name"] == "Dhaka City"
    assert calc(api_client, district="Dhaka", area="Savar", subtotal="1").json()["zone_name"] == "Outer Dhaka"


def test_the_global_threshold_makes_it_free(api_client, seeded):
    set_global_threshold("1500.00")
    below = calc(api_client, district="Dhaka", subtotal="1499.99").json()
    at = calc(api_client, district="Dhaka", subtotal="1500").json()
    assert below["charge"] == "70.00" and below["free_shipping_threshold"] == "1500.00"
    assert at["charge"] == "0.00" and at["is_free"] and at["free_shipping_reason"] == "free_shipping_threshold"


def test_a_zone_threshold_override_applies(api_client, seeded):
    set_global_threshold("5000.00")
    DeliveryZone.objects.filter(slug="outside-dhaka").update(free_shipping_threshold="1000.00")
    assert calc(api_client, district="Sylhet", subtotal="1000").json()["is_free"] is True
    assert calc(api_client, district="Dhaka", subtotal="1000").json()["is_free"] is False


def test_delivery_method_extra_is_added(api_client, seeded):
    method = DeliveryMethod.objects.get(slug="express")
    method.is_active = True
    method.save()
    body = calc(api_client, district="Dhaka", subtotal="10", delivery_method="express").json()
    assert body["charge"] == "170.00" and body["zone_charge"] == "70.00"
    assert body["delivery_method"] == {"id": method.id, "slug": "express", "name": "Express", "extra_charge": "100.00"}


def test_an_unavailable_method_is_a_400_on_that_field(api_client, seeded):
    r = calc(api_client, district="Dhaka", subtotal="10", delivery_method="express")  # seeded inactive
    assert r.status_code == 400 and "delivery_method" in r.json()["error"]["details"]
    assert calc(api_client, district="Dhaka", subtotal="10", delivery_method="nope").status_code == 400


def test_the_carts_subtotal_is_used_when_none_is_sent(api_client, seeded):
    guest_cart(api_client, price="1200.00", quantity=2)
    set_global_threshold("2400.00")
    body = calc(api_client, district="Dhaka").json()
    assert body["is_free"] is True and body["free_shipping_reason"] == "free_shipping_threshold"


def test_a_free_shipping_coupon_on_the_cart_makes_delivery_free(api_client, seeded):
    guest_cart(api_client, price="1000.00")
    CouponFactory(code="SHIPFREE", type="flat", amount="10.00", free_shipping=True)
    assert api_client.post(COUPON, {"code": "SHIPFREE"}, format="json").status_code == 200
    body = calc(api_client, district="Sylhet").json()
    assert body["charge"] == "0.00" and body["free_shipping_reason"] == "coupon_free_shipping"


def test_a_coupon_that_no_longer_applies_no_longer_frees_shipping(api_client, seeded):
    guest_cart(api_client, price="1000.00")
    coupon = CouponFactory(code="SHIPFREE", type="flat", amount="10.00", free_shipping=True)
    api_client.post(COUPON, {"code": "SHIPFREE"}, format="json")
    coupon.is_active = False
    coupon.save()  # the cart keeps the code but the coupon stopped being valid
    assert calc(api_client, district="Sylhet").json()["charge"] == "120.00"


def test_an_ordinary_coupon_does_not_free_shipping(api_client, seeded):
    guest_cart(api_client, price="1000.00")
    CouponFactory(code="TEN", type="flat", amount="10.00", free_shipping=False)
    api_client.post(COUPON, {"code": "TEN"}, format="json")
    assert calc(api_client, district="Sylhet").json()["charge"] == "120.00"


def test_a_sent_subtotal_wins_over_the_carts(api_client, seeded):
    guest_cart(api_client, price="10.00")
    set_global_threshold("500.00")
    assert calc(api_client, district="Dhaka", subtotal="500").json()["is_free"] is True


def test_no_subtotal_and_no_cart_is_a_400(api_client, seeded):
    r = calc(api_client, district="Dhaka")
    assert r.status_code == 400 and "subtotal" in r.json()["error"]["details"]


def test_district_is_required(api_client, seeded):
    r = calc(api_client, subtotal="100")
    assert r.status_code == 400 and "district" in r.json()["error"]["details"]
    assert calc(api_client, district="", subtotal="100").status_code == 400


@pytest.mark.parametrize("bad", ["abc", "-1", "NaN", "Infinity"])
def test_a_bad_subtotal_is_a_400_not_a_500(api_client, seeded, bad):
    r = calc(api_client, district="Dhaka", subtotal=bad)
    assert r.status_code == 400 and "subtotal" in r.json()["error"]["details"]


def test_an_unknown_district_still_gets_a_price(api_client, seeded):
    assert calc(api_client, district="Atlantis", subtotal="10").json()["charge"] == "120.00"


def test_the_client_cannot_set_the_charge(api_client, seeded):
    body = calc(api_client, district="Dhaka", subtotal="10", charge="0", shipping_charge="0", zone_id=999, is_free=True).json()
    assert body["charge"] == "70.00" and body["is_free"] is False


def test_it_works_for_a_logged_in_customer_with_their_own_cart(auth_client, customer, seeded):
    client = auth_client(customer)
    product = ProductFactory(regular_price="800.00", stock_quantity=10)
    client.post(ITEMS, {"product_id": product.id, "quantity": 1}, format="json")
    set_global_threshold("800.00")
    assert calc(client, district="Dhaka").json()["is_free"] is True


def test_a_broken_token_is_treated_as_a_guest(api_client, seeded):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
    assert calc(api_client, district="Dhaka", subtotal="5").status_code == 200


def test_with_no_default_zone_the_calculator_says_503_not_500(api_client):
    DeliveryZoneFactory()
    r = calc(api_client, district="Dhaka", subtotal="5")
    assert r.status_code == 503 and r.json()["error"]["code"] == "shipping_not_configured"


def test_calculating_hits_the_database_only_for_the_cart_not_for_zones(api_client, seeded, django_assert_num_queries):
    set_global_threshold("100.00")
    services.calculate_shipping({"district": "Dhaka"}, Decimal("10"))  # warms the zone cache and the site-settings cache
    with django_assert_num_queries(0):
        services.calculate_shipping({"district": "Dhaka"}, Decimal("10"))
