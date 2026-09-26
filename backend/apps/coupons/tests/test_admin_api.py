from datetime import timedelta

import pytest
from django.utils import timezone

from apps.catalog.tests.factories import BrandFactory, CategoryFactory, ProductFactory
from apps.coupons.models import Coupon

from .factories import CouponFactory, CouponUsageFactory

pytestmark = pytest.mark.django_db

COUPONS = "/api/v1/admin/coupons/"
USAGES = "/api/v1/admin/coupon-usages/"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


def details(response):
    return response.json()["error"]["details"]


# --- access control -------------------------------------------------------------------------------


@pytest.mark.parametrize("url", [COUPONS, USAGES])
def test_only_staff_may_use_coupon_endpoints(api_client, auth_client, customer, cce_user, url):
    assert api_client.get(url).status_code == 401
    assert auth_client(customer).get(url).status_code == 403
    # CCE reads the coupon list (read-only); the usage history stays Admin only
    assert auth_client(cce_user).get(url).status_code == (200 if url == COUPONS else 403)


def test_cce_cannot_write_or_delete_coupons(auth_client, cce_user):
    coupon = CouponFactory()
    client = auth_client(cce_user)
    assert client.post(COUPONS, {"code": "X", "type": "flat", "amount": "10"}, format="json").status_code == 403
    assert client.patch(f"{COUPONS}{coupon.id}/", {"is_active": False}, format="json").status_code == 403
    assert client.delete(f"{COUPONS}{coupon.id}/").status_code == 403
    assert Coupon.objects.get().is_active


# --- create -----------------------------------------------------------------------------------------


def test_create_a_flat_coupon(admin_client):
    r = admin_client.post(COUPONS, {"code": "welcome100", "type": "flat", "amount": "100.00", "description": "Welcome"}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["code"] == "WELCOME100" and body["type"] == "flat" and body["amount"] == "100.00"
    assert body["is_active"] is True and body["usage_count"] == 0 and body["products"] == []


def test_create_a_percentage_coupon_with_everything(admin_client):
    product, category, brand = ProductFactory(), CategoryFactory(), BrandFactory()
    now = timezone.now()
    payload = {
        "code": "SUMMER20", "type": "percentage", "amount": "20.00", "max_discount_amount": "500.00",
        "min_order_amount": "1500.00", "start_at": now.isoformat(), "expiry_at": (now + timedelta(days=30)).isoformat(),
        "total_usage_limit": 100, "per_customer_usage_limit": 1,
        "product_ids": [product.id], "category_ids": [category.id], "brand_ids": [brand.id],
        "exclude_sale_items": True, "first_order_only": True, "free_shipping": True,
    }
    r = admin_client.post(COUPONS, payload, format="json")
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body["max_discount_amount"] == "500.00" and body["min_order_amount"] == "1500.00"
    assert body["total_usage_limit"] == 100 and body["per_customer_usage_limit"] == 1
    assert [p["id"] for p in body["products"]] == [product.id]
    assert [c["id"] for c in body["categories"]] == [category.id]
    assert [b["id"] for b in body["brands"]] == [brand.id]
    assert body["exclude_sale_items"] and body["first_order_only"] and body["free_shipping"]


def test_code_uniqueness_is_case_insensitive(admin_client):
    CouponFactory(code="WELCOME")
    r = admin_client.post(COUPONS, {"code": "welcome", "type": "flat", "amount": "10"}, format="json")
    assert r.status_code == 400 and "code" in details(r)
    assert Coupon.objects.count() == 1


def test_blank_or_whitespace_code_rejected(admin_client):
    for code in ("", "   "):
        r = admin_client.post(COUPONS, {"code": code, "type": "flat", "amount": "10"}, format="json")
        assert r.status_code == 400 and "code" in details(r)


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"type": "percentage", "amount": "150"}, "amount"),
        ({"type": "flat", "amount": "0"}, "amount"),
        ({"type": "flat", "amount": "-5"}, "amount"),
        ({"type": "flat", "amount": "10", "max_discount_amount": "50"}, "max_discount_amount"),
        ({"type": "bogus", "amount": "10"}, "type"),
        ({"type": "flat", "amount": "10", "min_order_amount": "-1"}, "min_order_amount"),
        ({"type": "flat", "amount": "10", "total_usage_limit": -1}, "total_usage_limit"),
    ],
)
def test_validation_errors(admin_client, payload, field):
    r = admin_client.post(COUPONS, {"code": "X1", **payload}, format="json")
    assert r.status_code == 400 and field in details(r), r.json()


def test_expiry_must_be_after_start(admin_client):
    now = timezone.now()
    r = admin_client.post(
        COUPONS, {"code": "X1", "type": "flat", "amount": "10", "start_at": now.isoformat(), "expiry_at": now.isoformat()}, format="json"
    )
    assert r.status_code == 400 and "expiry_at" in details(r)


def test_unknown_product_category_brand_ids_are_rejected(admin_client):
    for field in ("product_ids", "category_ids", "brand_ids"):
        r = admin_client.post(COUPONS, {"code": "X1", "type": "flat", "amount": "10", field: [999999]}, format="json")
        assert r.status_code == 400 and field in details(r)


def test_percentage_of_exactly_100_is_allowed(admin_client):
    assert admin_client.post(COUPONS, {"code": "FREE", "type": "percentage", "amount": "100"}, format="json").status_code == 201


# --- read / list ------------------------------------------------------------------------------------------


def test_list_includes_inactive_and_is_paginated(admin_client):
    CouponFactory(is_active=True), CouponFactory(is_active=False)
    body = admin_client.get(COUPONS).json()
    assert set(body) == {"count", "next", "previous", "results"} and body["count"] == 2


def test_filters_search_and_ordering(admin_client):
    CouponFactory(code="SUMMER", type="percentage", amount="10", is_active=False)
    CouponFactory(code="WINTER", type="flat", is_active=True)
    assert admin_client.get(f"{COUPONS}?is_active=false").json()["count"] == 1
    assert admin_client.get(f"{COUPONS}?type=flat").json()["results"][0]["code"] == "WINTER"
    assert [c["code"] for c in admin_client.get(f"{COUPONS}?search=summ").json()["results"]] == ["SUMMER"]
    assert [c["code"] for c in admin_client.get(f"{COUPONS}?ordering=code").json()["results"]] == ["SUMMER", "WINTER"]


def test_retrieve_and_404(admin_client):
    coupon = CouponFactory()
    assert admin_client.get(f"{COUPONS}{coupon.id}/").json()["code"] == coupon.code
    assert admin_client.get(f"{COUPONS}99999/").status_code == 404


def test_usage_count_is_reported(admin_client):
    coupon = CouponFactory()
    CouponUsageFactory.create_batch(3, coupon=coupon)
    assert admin_client.get(f"{COUPONS}{coupon.id}/").json()["usage_count"] == 3


# --- update -----------------------------------------------------------------------------------------------------


def test_patch_updates_only_sent_fields(admin_client):
    coupon = CouponFactory(code="KEEP", amount="50.00", description="orig")
    r = admin_client.patch(f"{COUPONS}{coupon.id}/", {"is_active": False}, format="json")
    assert r.status_code == 200 and r.json()["is_active"] is False
    coupon.refresh_from_db()
    assert coupon.code == "KEEP" and coupon.description == "orig"


def test_patch_code_uniqueness_ignores_self_but_not_others(admin_client):
    mine = CouponFactory(code="MINE")
    CouponFactory(code="OTHER")
    assert admin_client.patch(f"{COUPONS}{mine.id}/", {"code": "mine"}, format="json").status_code == 200
    assert "code" in details(admin_client.patch(f"{COUPONS}{mine.id}/", {"code": "other"}, format="json"))


def test_patch_cross_field_rules_use_the_stored_values(admin_client):
    flat = CouponFactory(type="flat", amount="10.00")
    r = admin_client.patch(f"{COUPONS}{flat.id}/", {"max_discount_amount": "50"}, format="json")
    assert r.status_code == 400 and "max_discount_amount" in details(r)
    pct = CouponFactory(type="percentage", amount="10.00")
    assert "amount" in details(admin_client.patch(f"{COUPONS}{pct.id}/", {"amount": "500"}, format="json"))


def test_patch_replaces_and_clears_applicability(admin_client):
    a, b = ProductFactory(), ProductFactory()
    coupon = CouponFactory()
    coupon.products.set([a])
    r = admin_client.patch(f"{COUPONS}{coupon.id}/", {"product_ids": [b.id]}, format="json")
    assert [p["id"] for p in r.json()["products"]] == [b.id]
    assert admin_client.patch(f"{COUPONS}{coupon.id}/", {"product_ids": []}, format="json").json()["products"] == []


def test_patch_omitting_applicability_leaves_it_alone(admin_client):
    product = ProductFactory()
    coupon = CouponFactory()
    coupon.products.set([product])
    admin_client.patch(f"{COUPONS}{coupon.id}/", {"description": "x"}, format="json")
    assert list(coupon.products.values_list("id", flat=True)) == [product.id]


def test_put_not_supported(admin_client):
    assert admin_client.put(f"{COUPONS}{CouponFactory().id}/", {}, format="json").status_code == 405


# --- delete -------------------------------------------------------------------------------------------------------


def test_delete_an_unused_coupon(admin_client):
    coupon = CouponFactory()
    assert admin_client.delete(f"{COUPONS}{coupon.id}/").status_code == 204
    assert not Coupon.objects.exists()


def test_delete_a_used_coupon_is_a_409_not_a_500(admin_client):
    coupon = CouponFactory()
    CouponUsageFactory.create_batch(2, coupon=coupon)
    r = admin_client.delete(f"{COUPONS}{coupon.id}/")
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "coupon_has_usages" and error["details"] == {"usage_count": 2}
    assert Coupon.objects.filter(pk=coupon.pk).exists()


def test_a_used_coupon_can_be_deactivated_instead(admin_client):
    coupon = CouponFactory()
    CouponUsageFactory(coupon=coupon)
    assert admin_client.patch(f"{COUPONS}{coupon.id}/", {"is_active": False}, format="json").status_code == 200


# --- usage history --------------------------------------------------------------------------------------------------


def test_usage_history_lists_redemptions_with_fields(admin_client, customer):
    coupon = CouponFactory(code="HIST")
    CouponUsageFactory(coupon=coupon, user=customer, phone=customer.phone, order_reference="ORD-9", discount_amount="75.00")
    body = admin_client.get(USAGES).json()
    row = body["results"][0]
    assert body["count"] == 1
    assert row["coupon_code"] == "HIST" and row["order_reference"] == "ORD-9" and row["discount_amount"] == "75.00"
    assert row["phone"] == customer.phone and row["user_name"] == customer.full_name
    assert set(row) == {"id", "coupon_code", "user_name", "phone", "order_reference", "discount_amount", "created_at"}


def test_usage_history_filters_by_coupon_and_is_read_only(admin_client):
    a, b = CouponFactory(), CouponFactory()
    CouponUsageFactory(coupon=a), CouponUsageFactory(coupon=b)
    assert admin_client.get(f"{USAGES}?coupon={a.id}").json()["count"] == 1
    assert admin_client.post(USAGES, {}, format="json").status_code == 405
    assert admin_client.delete(f"{USAGES}1/").status_code == 405


def test_guest_usage_has_no_user_name(admin_client):
    CouponUsageFactory(user=None, phone="01711111111")
    assert admin_client.get(USAGES).json()["results"][0]["user_name"] is None



def test_status_and_status_filter(admin_client):
    from datetime import timedelta

    from django.utils import timezone

    now = timezone.now()
    CouponFactory(code="LIVE")
    CouponFactory(code="OFF", is_active=False)
    CouponFactory(code="SOON", start_at=now + timedelta(days=2))
    CouponFactory(code="OLD", start_at=now - timedelta(days=9), expiry_at=now - timedelta(days=1))
    rows = {c["code"]: c["status"] for c in admin_client.get(COUPONS).json()["results"]}
    assert rows == {"LIVE": "active", "OFF": "inactive", "SOON": "scheduled", "OLD": "expired"}
    for status, code in [("active", "LIVE"), ("inactive", "OFF"), ("scheduled", "SOON"), ("expired", "OLD")]:
        assert [c["code"] for c in admin_client.get(f"{COUPONS}?status={status}").json()["results"]] == [code]



def test_cce_can_read_coupons_but_not_change_them(auth_client, cce_user):
    coupon = CouponFactory(code="READONLY")
    client = auth_client(cce_user)
    assert [c["code"] for c in client.get(COUPONS).json()["results"]] == ["READONLY"]
    assert client.get(f"{COUPONS}{coupon.id}/").json()["code"] == "READONLY"
    assert client.post(COUPONS, {"code": "NEW", "type": "flat", "amount": "10"}, format="json").status_code == 403
    assert client.patch(f"{COUPONS}{coupon.id}/", {"is_active": False}, format="json").status_code == 403
    assert client.delete(f"{COUPONS}{coupon.id}/").status_code == 403
    assert client.get("/api/v1/admin/coupon-usages/").status_code == 403
