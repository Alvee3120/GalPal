"""Cart promotions (Buy X Get Y% off, Buy X Get Y free, lowest-priced free, 3 for 2, fixed bundle price).

The engine is exercised directly (through the real live-discount index), then through the cart API, checkout and the
storefront endpoints, mirroring how the whole system is wired (apps.discounts.promotions).
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.models import Category, Product, ProductCategory
from apps.catalog.tests.factories import ProductFactory
from apps.coupons.tests.factories import CouponFactory
from apps.discounts import services
from apps.discounts.models import Discount, DiscountKind
from apps.discounts.promotions import LineIn, apply_promotions
from apps.orders.models import Order
from apps.orders.tests.helpers import CART_COUPON, add_to_cart, place

pytestmark = pytest.mark.django_db

D = Decimal
A = "/api/v1/admin/discounts/"


@pytest.fixture(autouse=True)
def _fresh_index():
    services.invalidate()
    yield
    services.invalidate()


@pytest.fixture(autouse=True)
def _shipping_defaults(db):
    """Inside Dhaka 70 / Outside Dhaka 120, like the seed leaves them (checkout needs real zones)."""
    from apps.shipping import seed
    from apps.shipping.models import DeliveryMethod, DeliveryZone, District, ShippingChargeHistory, ZoneDistrict

    DeliveryZone.objects.all().delete()
    DeliveryMethod.objects.all().delete()
    ShippingChargeHistory.objects.all().delete()
    seed.seed_all(District, DeliveryZone, ZoneDistrict, DeliveryMethod, ShippingChargeHistory)


def window(start_hours=-1, end_hours=48):
    now = timezone.now()
    return {"starts_at": now + timedelta(hours=start_hours), "ends_at": now + timedelta(hours=end_hours)}


def make(kind, *, products=(), categories=(), target="products", active=True, start_hours=-1, end_hours=48, **config):
    discount = Discount.objects.create(
        name=f"{kind}", kind=kind, target_type=target, is_active=active, **window(start_hours, end_hours), **config
    )
    if products:
        discount.products.set(products)
    if categories:
        discount.categories.set(categories)
    services.invalidate()
    return discount


def product(price="400.00", **kw):
    return ProductFactory(status="published", regular_price=D(price), discount_price=None, stock_quantity=50, manage_stock=True, **kw)


def line(p, quantity, price=None):
    return LineIn(key=(p.id, None), product_id=p.id, unit_price=D(price if price is not None else p.effective_price), quantity=quantity)


# --- 1. Buy X items, get Y% off ------------------------------------------------------------------------------------


def test_buy_three_get_20_percent_off():
    p = product("400.00")
    make(DiscountKind.BUY_X_GET_Y_PERCENT, products=[p], min_quantity=3, percent_off=D("20"))
    result = apply_promotions([line(p, 3)])
    assert result.total == D("240.00")
    assert result.by_line[(p.id, None)]["promotion_discount"] == D("240.00")


def test_buy_x_get_y_percent_below_minimum_does_nothing():
    p = product("400.00")
    make(DiscountKind.BUY_X_GET_Y_PERCENT, products=[p], min_quantity=3, percent_off=D("20"))
    assert apply_promotions([line(p, 2)]).total == D("0.00")


# --- 2. Buy X, get Y free ------------------------------------------------------------------------------------------


def test_buy_two_get_one_free_discounts_the_cheapest_unit():
    p = product("400.00")
    make(DiscountKind.BUY_X_GET_Y_FREE, products=[p], min_quantity=2, free_quantity=1)
    result = apply_promotions([line(p, 3)])
    assert result.total == D("400.00")
    assert result.by_line[(p.id, None)]["free_quantity"] == 1


def test_buy_x_get_y_free_repeats_only_when_allowed():
    p = product("400.00")
    make(DiscountKind.BUY_X_GET_Y_FREE, products=[p], min_quantity=2, free_quantity=1, allow_repeat=True)
    assert apply_promotions([line(p, 6)]).total == D("800.00")
    Discount.objects.all().delete()
    services.invalidate()
    make(DiscountKind.BUY_X_GET_Y_FREE, products=[p], min_quantity=2, free_quantity=1, allow_repeat=False)
    assert apply_promotions([line(p, 6)]).total == D("400.00")


# --- 3. Buy X, get the lowest-priced item free ---------------------------------------------------------------------


def test_buy_three_get_lowest_priced_item_free():
    a, b, c = product("500.00"), product("400.00"), product("300.00")
    make(DiscountKind.LOWEST_FREE, products=[a, b, c], min_quantity=3)
    result = apply_promotions([line(a, 1), line(b, 1), line(c, 1)])
    assert result.total == D("300.00")
    assert result.by_line[(c.id, None)]["free_quantity"] == 1


# X = 2 means the group is 2 units and the cheaper of the two is free (the customer pays for the higher one).
def test_lowest_free_x2_acceptance():
    a, b = product("800.00"), product("500.00")
    make(DiscountKind.LOWEST_FREE, products=[a, b], min_quantity=2)
    result = apply_promotions([line(a, 1), line(b, 1)])
    assert result.total == D("500.00")  # 1300 -> 800
    assert result.by_line[(b.id, None)]["free_quantity"] == 1  # the cheaper unit is the free one
    assert result.by_line.get((a.id, None), {}).get("free_quantity", 0) == 0


def test_lowest_free_x2_second_example():
    a, b = product("400.00"), product("250.00")
    make(DiscountKind.LOWEST_FREE, products=[a, b], min_quantity=2)
    assert apply_promotions([line(a, 1), line(b, 1)]).total == D("250.00")  # 650 -> 400


def test_lowest_free_x2_three_units_qualify_once():
    a, b, c = product("800.00"), product("500.00"), product("600.00")
    make(DiscountKind.LOWEST_FREE, products=[a, b, c], min_quantity=2)
    result = apply_promotions([line(a, 1), line(b, 1), line(c, 1)])
    assert result.total == D("500.00")  # one complete pair; the leftover unit is not paired
    assert sum(row["free_quantity"] for row in result.by_line.values()) == 1


def test_lowest_free_x2_four_units_two_free():
    a, b = product("800.00"), product("500.00")
    make(DiscountKind.LOWEST_FREE, products=[a, b], min_quantity=2)
    result = apply_promotions([line(a, 2), line(b, 2)])
    # Two groups, cheapest-first: (500, 500) and (800, 800) -> the 500 and the 800 are free.
    assert sum(row["free_quantity"] for row in result.by_line.values()) == 2
    assert result.total == D("1300.00")


def test_lowest_free_never_frees_an_ineligible_product():
    a, b, other = product("800.00"), product("500.00"), product("100.00")
    make(DiscountKind.LOWEST_FREE, products=[a, b], min_quantity=2)
    result = apply_promotions([line(a, 1), line(b, 1), line(other, 5)])
    assert result.total == D("500.00")  # the cheap ineligible unit is never made free
    assert result.by_line.get((other.id, None), {}).get("free_quantity", 0) == 0


def test_lowest_free_uses_variant_prices():
    a = product("900.00")
    make(DiscountKind.LOWEST_FREE, products=[a], min_quantity=2)
    result = apply_promotions([
        LineIn(key=(a.id, 11), product_id=a.id, unit_price=D("900"), quantity=1),
        LineIn(key=(a.id, 12), product_id=a.id, unit_price=D("300"), quantity=1),
    ])
    assert result.total == D("300.00")  # the cheaper variant is free



# --- 4. 3 for 2 ----------------------------------------------------------------------------------------------------


def test_three_for_two_once_and_repeated():
    p = product("400.00")
    make(DiscountKind.THREE_FOR_TWO, products=[p])
    assert apply_promotions([line(p, 3)]).total == D("400.00")
    assert apply_promotions([line(p, 6)]).total == D("800.00")


# --- 5 & 6 & 7. Fixed bundle price ---------------------------------------------------------------------------------


def test_bundle_price_is_the_group_total_payable():
    a, b, c = product("500.00"), product("400.00"), product("300.00")
    make(DiscountKind.BUNDLE_PRICE, products=[a, b, c], min_quantity=3, bundle_price=D("1000"))
    result = apply_promotions([line(a, 1), line(b, 1), line(c, 1)])
    assert result.total == D("200.00")
    assert sum((row["promotion_discount"] for row in result.by_line.values()), D("0.00")) == result.total


def test_bundle_price_never_raises_the_payable_price():
    a, b, c = product("300.00"), product("200.00"), product("100.00")  # subtotal 600 < 1000
    make(DiscountKind.BUNDLE_PRICE, products=[a, b, c], min_quantity=3, bundle_price=D("1000"))
    assert apply_promotions([line(a, 1), line(b, 1), line(c, 1)]).total == D("0.00")


def test_incomplete_group_gets_no_bundle_discount():
    a, b, c = product("500.00"), product("400.00"), product("300.00")
    make(DiscountKind.BUNDLE_PRICE, products=[a, b, c], min_quantity=3, bundle_price=D("1000"))
    assert apply_promotions([line(a, 1), line(b, 1)]).total == D("0.00")


# --- 9. Mixed eligible / ineligible, variants, scheduling, conflicts -----------------------------------------------


def test_only_eligible_products_count():
    eligible, other = product("400.00"), product("999.00")
    make(DiscountKind.BUY_X_GET_Y_PERCENT, products=[eligible], min_quantity=3, percent_off=D("20"))
    result = apply_promotions([line(eligible, 3), line(other, 5)])
    assert result.total == D("240.00")


def test_category_promotion_covers_sub_categories():
    parent = Category.objects.create(name="Skincare", slug="skincare")
    child = Category.objects.create(name="Serums", slug="serums", parent=parent)
    inside, outside = product("400.00"), product("400.00")
    ProductCategory.objects.create(product=inside, category=child, is_primary=True)
    make(DiscountKind.THREE_FOR_TWO, target="category", categories=[parent])
    assert apply_promotions([line(inside, 3)]).total == D("400.00")
    assert apply_promotions([line(outside, 3)]).total == D("0.00")


def test_scheduled_and_inactive_promotions_do_not_apply():
    p = product("400.00")
    make(DiscountKind.THREE_FOR_TWO, products=[p], start_hours=3)
    make(DiscountKind.THREE_FOR_TWO, products=[p], active=False)
    assert apply_promotions([line(p, 3)]).total == D("0.00")


def test_a_unit_never_receives_two_free_item_offers():
    p = product("400.00")
    make(DiscountKind.THREE_FOR_TWO, products=[p])  # consumes all 3
    make(DiscountKind.BUY_X_GET_Y_FREE, products=[p], min_quantity=2, free_quantity=1)
    # The first (product-targeted, lower id) rule consumes the units; the second has none left.
    assert apply_promotions([line(p, 3)]).total == D("400.00")


# --- storefront: effective price is untouched, section lists eligible products --------------------------------------


def test_cart_promotion_does_not_change_effective_price_and_appears_on_storefront(api_client):
    p = product("400.00")
    d = make(DiscountKind.BUY_X_GET_Y_FREE, products=[p], min_quantity=2, free_quantity=1)
    assert Product.objects.get(pk=p.pk).effective_price == D("400.00")  # single-product price untouched
    active = api_client.get("/api/v1/discounts/active/").json()
    row = next((x for x in active if x["id"] == d.id), None)
    assert row is not None and row["label"] == "Buy 2, get 1 free" and row["product_count"] == 1
    listing = api_client.get(f"/api/v1/products/?discount={d.id}").json()
    assert [item["id"] for item in listing["results"]] == [p.id]
    d.is_active = False
    d.save()
    services.invalidate()
    assert api_client.get(f"/api/v1/products/?discount={d.id}").json()["count"] == 0


# --- cart API + checkout --------------------------------------------------------------------------------------------


def test_cart_payload_carries_promotion_fields(api_client):
    p = product("400.00")
    make(DiscountKind.BUY_X_GET_Y_FREE, products=[p], min_quantity=2, free_quantity=1)
    add_to_cart(api_client, p, quantity=3)
    body = api_client.get("/api/v1/cart/").json()
    assert D(body["promotion_discount"]) == D("400.00")
    assert body["promotions"][0]["label"] == "Buy 2, get 1 free"
    assert body["items"][0]["free_quantity"] == 1
    assert D(body["total"]) == D(body["subtotal"]) - D("400.00") - D(body["discount"])


def test_checkout_snapshots_the_promotion_and_totals(api_client):
    p = product("400.00")
    make(DiscountKind.BUY_X_GET_Y_PERCENT, products=[p], min_quantity=3, percent_off=D("20"))
    response = place(api_client, p, quantity=3)
    assert response.status_code == 201
    order = Order.objects.get()
    assert order.promotion_discount == D("240.00")
    assert order.grand_total == D("400.00") * 3 - D("240.00") + D("70.00")  # 1200 - 240 + 70
    item = order.items.get()
    assert item.promotion_discount == D("240.00") and item.line_total == D("1200.00")
    assert order.applied_promotions and order.applied_promotions[0]["kind"] == "buy_x_get_y_percent"


def test_checkout_stores_free_quantity_for_a_free_item_order(api_client):
    p = product("400.00")
    make(DiscountKind.THREE_FOR_TWO, products=[p])
    assert place(api_client, p, quantity=3).status_code == 201
    order = Order.objects.get()
    assert order.promotion_discount == D("400.00")
    assert order.items.get().free_quantity == 1


def test_the_client_cannot_dictate_the_promotion(api_client):
    p = product("400.00")
    make(DiscountKind.BUY_X_GET_Y_PERCENT, products=[p], min_quantity=3, percent_off=D("20"))
    response = place(api_client, p, quantity=3, promotion_discount="9999", discount="9999", grand_total="1", subtotal="1")
    assert response.status_code == 201
    order = Order.objects.get()
    assert order.promotion_discount == D("240.00") and order.subtotal == D("1200.00")


# --- 13. Coupon compatibility (promotion first, coupon on the remainder) -------------------------------------------


def test_a_coupon_applies_after_the_promotion(api_client):
    p = product("400.00")
    make(DiscountKind.BUY_X_GET_Y_FREE, products=[p], min_quantity=2, free_quantity=1)  # 3 units -> 400 off
    CouponFactory(code="FLAT100", type="flat", amount=D("100.00"))
    add_to_cart(api_client, p, quantity=3)
    assert api_client.post(CART_COUPON, {"code": "FLAT100"}, format="json").status_code == 200
    body = api_client.get("/api/v1/cart/").json()
    # coupon is computed on the post-promotion eligible subtotal (1200 - 400 = 800); flat 100 off
    assert D(body["discount"]) == D("100.00")
    assert D(body["total"]) == D("1200.00") - D("400.00") - D("100.00")


# --- 17. Historical orders survive promotion edits -----------------------------------------------------------------


def test_editing_a_promotion_leaves_historical_orders_unchanged(api_client):
    p = product("400.00")
    d = make(DiscountKind.THREE_FOR_TWO, products=[p])
    place(api_client, p, quantity=3)
    order = Order.objects.get()
    d.kind = DiscountKind.BUNDLE_PRICE
    d.min_quantity = 3
    d.bundle_price = D("100")
    d.is_active = False
    d.save()
    services.invalidate()
    order.refresh_from_db()
    assert order.promotion_discount == D("400.00")
    assert order.items.get().free_quantity == 1
    assert order.grand_total == D("1200.00") - D("400.00") + D("70.00")


# --- 13/Admin: validation and authorization ------------------------------------------------------------------------


@pytest.mark.parametrize("kind,config,saved", [
    ("buy_x_get_y_percent", {"min_quantity": 3, "percent_off": "20"}, {"min_quantity": 3, "percent_off": D("20")}),
    ("buy_x_get_y_free", {"min_quantity": 2, "free_quantity": 1}, {"min_quantity": 2, "free_quantity": 1}),
    ("lowest_free", {"min_quantity": 3}, {"min_quantity": 3}),
    ("bundle_price", {"min_quantity": 3, "bundle_price": "1000"}, {"min_quantity": 3, "bundle_price": D("1000")}),
])
def test_each_cart_kind_saves_its_own_config(auth_client, admin_user, kind, config, saved):
    p = product("400.00")
    starts, ends = window()["starts_at"], window()["ends_at"]
    body = {"name": "offer", "kind": kind, "target_type": "products", "product_ids": [p.pk],
            "starts_at": starts.isoformat(), "ends_at": ends.isoformat(), **config}
    response = auth_client(admin_user).post(A, body, format="json")
    assert response.status_code == 201, response.json()
    d = Discount.objects.get(pk=response.json()["id"])
    for field, expected in saved.items():
        assert getattr(d, field) == expected, (field, getattr(d, field))
    assert d.value is None  # a cart promotion prices no single product


def test_only_admin_manages_promotions(api_client, auth_client, cce_user, customer, admin_user):
    p = product("400.00")
    body = {"name": "3 for 2", "kind": "three_for_two", "target_type": "products", "product_ids": [p.pk], **window()}
    body = {**body, "starts_at": body["starts_at"].isoformat(), "ends_at": body["ends_at"].isoformat()}
    assert api_client.post(A, body, format="json").status_code == 401
    for user in (cce_user, customer):
        assert auth_client(user).post(A, body, format="json").status_code == 403
    assert auth_client(admin_user).post(A, body, format="json").status_code == 201


@pytest.mark.parametrize("kind,config", [
    ("buy_x_get_y_percent", {"min_quantity": 3, "percent_off": "0"}),      # percent must be > 0
    ("buy_x_get_y_percent", {"min_quantity": 3, "percent_off": "150"}),    # and <= 100
    ("buy_x_get_y_percent", {"percent_off": "20"}),                        # min quantity required
    ("buy_x_get_y_free", {"min_quantity": 2}),                             # free quantity required
    ("bundle_price", {"min_quantity": 3}),                                 # bundle price required
    ("lowest_free", {}),                                                   # min quantity required
])
def test_invalid_cart_promotions_are_rejected(auth_client, admin_user, kind, config):
    p = product("400.00")
    starts, ends = window()["starts_at"], window()["ends_at"]
    body = {"name": "x", "kind": kind, "target_type": "products", "product_ids": [p.pk],
            "starts_at": starts.isoformat(), "ends_at": ends.isoformat(), **config}
    assert auth_client(admin_user).post(A, body, format="json").status_code == 400


def test_a_three_for_two_promotion_needs_no_quantity_fields(auth_client, admin_user):
    p = product("400.00")
    starts, ends = window()["starts_at"], window()["ends_at"]
    body = {"name": "3 for 2", "kind": "three_for_two", "target_type": "products", "product_ids": [p.pk],
            "starts_at": starts.isoformat(), "ends_at": ends.isoformat()}
    assert auth_client(admin_user).post(A, body, format="json").status_code == 201
