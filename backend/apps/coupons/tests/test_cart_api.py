import pytest

from apps.cart.models import Cart
from apps.catalog.tests.factories import ProductFactory

from .factories import CouponFactory, CouponUsageFactory

pytestmark = pytest.mark.django_db

CART = "/api/v1/cart/"
ITEMS = "/api/v1/cart/items/"
COUPON = "/api/v1/cart/coupon/"


def guest_with(client, price="1000.00", quantity=1, **product_kwargs):
    product = ProductFactory(regular_price=price, stock_quantity=100, **product_kwargs)
    body = client.post(ITEMS, {"product_id": product.id, "quantity": quantity}, format="json").json()
    client.credentials(HTTP_X_CART_TOKEN=body["cart_token"])
    return product


def test_apply_a_flat_coupon(api_client):
    guest_with(api_client)
    CouponFactory(code="SAVE100", amount="100.00")
    r = api_client.post(COUPON, {"code": "SAVE100"}, format="json")
    assert r.status_code == 200
    body = r.json()
    assert body["discount"] == "100.00" and body["subtotal"] == "1000.00" and body["total"] == "900.00"
    assert body["coupon"] == {"code": "SAVE100", "is_valid": True, "message": ""}


def test_apply_a_percentage_coupon_with_a_cap(api_client):
    guest_with(api_client, price="2000.00")
    CouponFactory(code="TWENTY", type="percentage", amount="20.00", max_discount_amount="150.00")
    body = api_client.post(COUPON, {"code": "TWENTY"}, format="json").json()
    assert body["discount"] == "150.00" and body["total"] == "1850.00"


def test_code_is_case_insensitive_and_trimmed(api_client):
    guest_with(api_client)
    CouponFactory(code="WELCOME", amount="50.00")
    assert api_client.post(COUPON, {"code": "  welcome "}, format="json").json()["coupon"]["code"] == "WELCOME"


def test_unknown_code_is_a_400_on_code(api_client):
    guest_with(api_client)
    r = api_client.post(COUPON, {"code": "NOPE"}, format="json")
    assert r.status_code == 400 and r.json()["error"]["details"] == {"code": ["Invalid coupon code."]}


def test_a_coupon_that_does_not_currently_apply_is_rejected_with_the_reason(api_client):
    guest_with(api_client, price="100.00")
    CouponFactory(code="BIG", min_order_amount="5000.00")
    r = api_client.post(COUPON, {"code": "BIG"}, format="json")
    assert r.status_code == 400 and "Minimum order amount" in r.json()["error"]["details"]["code"][0]


def test_code_is_required(api_client):
    assert api_client.post(COUPON, {}, format="json").status_code == 400
    assert api_client.post(COUPON, {"code": ""}, format="json").status_code == 400


def test_applying_to_a_guest_with_no_cart_yet_creates_one_but_rejects_the_coupon(api_client):
    CouponFactory(code="SAVE100")
    r = api_client.post(COUPON, {"code": "SAVE100"}, format="json")
    assert r.status_code == 400  # an empty cart can't satisfy "applies to something in your cart"


def test_discount_follows_the_cart_as_it_changes(api_client):
    product = guest_with(api_client, price="500.00", quantity=1)
    CouponFactory(code="TEN", type="percentage", amount="10.00")
    assert api_client.post(COUPON, {"code": "TEN"}, format="json").json()["discount"] == "50.00"
    item_id = api_client.get(CART).json()["items"][0]["id"]
    body = api_client.patch(f"{ITEMS}{item_id}/", {"quantity": 4}, format="json").json()
    assert body["subtotal"] == "2000.00" and body["discount"] == "200.00" and body["total"] == "1800.00"
    assert product


def test_coupon_stays_attached_but_pauses_when_the_cart_drops_below_the_minimum(api_client):
    guest_with(api_client, price="1000.00", quantity=2)
    CouponFactory(code="BIG", amount="100.00", min_order_amount="1500.00")
    api_client.post(COUPON, {"code": "BIG"}, format="json")
    item_id = api_client.get(CART).json()["items"][0]["id"]

    below = api_client.patch(f"{ITEMS}{item_id}/", {"quantity": 1}, format="json").json()
    assert below["discount"] == "0.00" and below["total"] == "1000.00"
    assert below["coupon"]["code"] == "BIG" and below["coupon"]["is_valid"] is False
    assert "Minimum order amount" in below["coupon"]["message"]

    above = api_client.patch(f"{ITEMS}{item_id}/", {"quantity": 2}, format="json").json()  # resumes by itself
    assert above["discount"] == "100.00" and above["coupon"]["is_valid"] is True


def test_deactivating_a_coupon_stops_its_discount_immediately(api_client):
    guest_with(api_client)
    coupon = CouponFactory(code="SAVE100")
    api_client.post(COUPON, {"code": "SAVE100"}, format="json")
    coupon.is_active = False
    coupon.save()
    body = api_client.get(CART).json()
    assert body["discount"] == "0.00" and body["coupon"]["is_valid"] is False


def test_deleting_a_coupon_detaches_it_from_carts(api_client):
    guest_with(api_client)
    coupon = CouponFactory(code="SAVE100")
    api_client.post(COUPON, {"code": "SAVE100"}, format="json")
    coupon.delete()
    body = api_client.get(CART).json()
    assert body["coupon"] is None and body["discount"] == "0.00"


def test_remove_coupon(api_client):
    guest_with(api_client)
    CouponFactory(code="SAVE100")
    api_client.post(COUPON, {"code": "SAVE100"}, format="json")
    body = api_client.delete(COUPON).json()
    assert body["coupon"] is None and body["discount"] == "0.00" and body["total"] == "1000.00"


def test_remove_coupon_is_a_no_op_without_a_cart_or_coupon(api_client):
    assert api_client.delete(COUPON).status_code == 200
    guest_with(api_client)
    assert api_client.delete(COUPON).status_code == 200


def test_free_shipping_coupon_changes_the_shipping_estimate(api_client):
    guest_with(api_client)
    CouponFactory(code="SHIPFREE", amount="10.00", free_shipping=True)
    body = api_client.post(COUPON, {"code": "SHIPFREE"}, format="json").json()
    assert body["shipping"] == {"amount": "0.00", "note": "Free shipping (coupon applied)"}
    assert body["total"] == "990.00"


def test_free_shipping_is_not_granted_while_the_coupon_is_paused(api_client):
    guest_with(api_client, price="1000.00")
    CouponFactory(code="SHIPFREE", amount="10.00", free_shipping=True, min_order_amount="900.00")
    api_client.post(COUPON, {"code": "SHIPFREE"}, format="json")
    from apps.catalog.models import Product

    Product.objects.update(regular_price="100.00")  # cart now below the 900 minimum
    body = api_client.get(CART).json()
    assert body["shipping"]["amount"] is None and body["coupon"]["is_valid"] is False


def test_excluded_sale_items_are_not_discounted_via_the_api(api_client):
    guest_with(api_client, price="1000.00", discount_price="800.00")
    CouponFactory(code="NOSALE", type="percentage", amount="10.00", exclude_sale_items=True)
    r = api_client.post(COUPON, {"code": "NOSALE"}, format="json")
    assert r.status_code == 400  # the only item is on sale, so nothing is eligible


def test_stale_bearer_token_does_not_break_the_endpoint(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage.garbage.garbage")
    assert api_client.delete(COUPON).status_code == 200


# --- logged-in customers ----------------------------------------------------------------------------------


def test_logged_in_customer_can_apply_and_the_per_user_limit_is_enforced(auth_client, customer):
    client = auth_client(customer)
    product = ProductFactory(regular_price="1000.00", stock_quantity=10)
    client.post(ITEMS, {"product_id": product.id, "quantity": 1}, format="json")
    coupon = CouponFactory(code="ONCE", per_customer_usage_limit=1)
    CouponUsageFactory(coupon=coupon, user=customer, phone=customer.phone)
    r = client.post(COUPON, {"code": "ONCE"}, format="json")
    assert r.status_code == 400 and "maximum number of times" in r.json()["error"]["details"]["code"][0]


def test_the_coupon_survives_guest_cart_merge_on_login(api_client, customer, password):
    guest_with(api_client, price="1000.00")
    CouponFactory(code="SAVE100")
    api_client.post(COUPON, {"code": "SAVE100"}, format="json")
    token = api_client.get(CART).json()["cart_token"]
    login = type(api_client)()
    login.credentials(HTTP_X_CART_TOKEN=token)
    access = login.post("/api/v1/auth/login/", {"identifier": customer.phone, "password": password}, format="json").json()["access"]
    user_client = type(api_client)()
    user_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    body = user_client.get(CART).json()
    assert body["item_count"] == 1
    assert body["coupon"]["code"] == "SAVE100" and body["discount"] == "100.00"  # carried over
    assert not Cart.objects.filter(token=token).exists()


def test_merge_keeps_the_accounts_own_coupon_over_the_guests(api_client, customer, password):
    guest_with(api_client, price="1000.00")
    CouponFactory(code="GUESTS", amount="10.00")
    CouponFactory(code="MINE", amount="20.00")
    api_client.post(COUPON, {"code": "GUESTS"}, format="json")
    token = api_client.get(CART).json()["cart_token"]
    Cart.objects.create(user=customer, coupon=CouponFactory._meta.model.objects.get(code="MINE"))
    login = type(api_client)()
    login.credentials(HTTP_X_CART_TOKEN=token)
    access = login.post("/api/v1/auth/login/", {"identifier": customer.phone, "password": password}, format="json").json()["access"]
    user_client = type(api_client)()
    user_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    assert user_client.get(CART).json()["coupon"]["code"] == "MINE"
