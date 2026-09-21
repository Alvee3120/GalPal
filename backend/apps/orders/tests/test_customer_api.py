import pytest

from apps.accounts.tests.factories import UserFactory
from apps.catalog.models import StockMovement
from apps.catalog.tests.factories import ProductFactory
from apps.coupons.models import CouponUsage
from apps.coupons.tests.factories import CouponFactory
from apps.orders import services
from apps.orders.models import Order

from .helpers import code, new_order, payload, place

pytestmark = pytest.mark.django_db

ORDERS = "/api/v1/orders/"
TRACK = "/api/v1/orders/track/"


def url(order, suffix=""):
    return f"{ORDERS}{order.number}/{suffix}"


# --- my orders -----------------------------------------------------------------------------------------------------------------------


def test_anonymous_gets_401(api_client, customer):
    order = new_order(customer=customer)
    assert api_client.get(ORDERS).status_code == 401
    assert api_client.get(url(order)).status_code == 401
    assert api_client.post(url(order, "cancel/")).status_code == 401


def test_a_customer_sees_only_their_own_orders(auth_client, customer):
    mine = new_order(customer=customer)
    new_order(customer=UserFactory(), phone="01787654321")
    new_order()  # a guest order
    body = auth_client(customer).get(ORDERS).json()
    assert body["count"] == 1 and body["results"][0]["number"] == mine.number
    assert set(body["results"][0]) == {"number", "status", "payment_method", "payment_status", "item_count", "grand_total", "created_at"}


def test_the_list_is_newest_first_paginated_and_filterable(auth_client, customer, admin_user):
    first, second = new_order(customer=customer), new_order(customer=customer)
    services.change_status(first, "cancelled", user=admin_user)
    client = auth_client(customer)
    assert [o["number"] for o in client.get(ORDERS).json()["results"]] == [second.number, first.number]
    assert [o["number"] for o in client.get(f"{ORDERS}?status=cancelled").json()["results"]] == [first.number]
    assert client.get(f"{ORDERS}?page_size=1").json()["next"] is not None


def test_detail_shows_items_totals_shipping_and_a_public_timeline(auth_client, customer):
    order = new_order(customer=customer, quantity=2)
    body = auth_client(customer).get(url(order)).json()
    assert body["number"] == order.number and body["subtotal"] == "1000.00" and body["shipping_charge"] == "70.00"
    assert body["shipping_zone_name"] == "Inside Dhaka" and body["grand_total"] == "1070.00" and body["can_cancel"] is True
    assert body["items"][0]["quantity"] == 2 and body["items"][0]["product_name"]
    assert set(body["history"][0]) == {"status", "created_at"}
    for hidden in ("source", "source_note", "created_by", "notes", "ip_address", "is_manual"):
        assert hidden not in body


def test_the_order_number_is_case_insensitive(auth_client, customer):
    order = new_order(customer=customer)
    assert auth_client(customer).get(f"{ORDERS}{order.number.lower()}/").status_code == 200


def test_someone_elses_order_is_a_404_not_a_403(auth_client, customer):
    other = new_order(customer=UserFactory(), phone="01787654321")
    assert auth_client(customer).get(url(other)).status_code == 404
    assert auth_client(customer).post(url(other, "cancel/")).status_code == 404


def test_a_guest_order_is_not_in_a_customers_list_even_with_the_same_phone(auth_client, customer):
    new_order(phone=customer.phone)
    assert auth_client(customer).get(ORDERS).json()["count"] == 0


# --- cancelling ---------------------------------------------------------------------------------------------------------------------------


def test_a_customer_cancels_a_pending_order_and_gets_stock_and_coupon_back(auth_client, customer):
    CouponFactory(code="SAVE50", amount="50.00")
    product = ProductFactory(stock_quantity=10, regular_price="500.00")
    order = new_order(customer=customer, product=product, quantity=3, coupon="SAVE50")
    r = auth_client(customer).post(url(order, "cancel/"), {"note": "changed my mind"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "cancelled" and r.json()["can_cancel"] is False
    product.refresh_from_db()
    assert product.stock_quantity == 10 and CouponUsage.objects.count() == 0
    assert Order.objects.get(pk=order.pk).history.last().note == "changed my mind"


def test_cancelling_a_confirmed_order_is_allowed(auth_client, customer, admin_user):
    order = new_order(customer=customer)
    services.change_status(order, "confirmed", user=admin_user)
    assert auth_client(customer).post(url(order, "cancel/")).status_code == 200


@pytest.mark.parametrize("status", ["processing", "shipped", "delivered"])
def test_cancelling_once_processing_has_started_is_a_409(auth_client, customer, status):
    order = new_order(customer=customer)
    Order.objects.filter(pk=order.pk).update(status=status)
    r = auth_client(customer).post(url(order, "cancel/"))
    assert r.status_code == 409 and code(r) == "not_cancellable"
    assert Order.objects.get(pk=order.pk).status == status


def test_cancelling_twice_is_a_409_and_restores_stock_once(auth_client, customer):
    product = ProductFactory(stock_quantity=10)
    order = new_order(customer=customer, product=product, quantity=2)
    client = auth_client(customer)
    assert client.post(url(order, "cancel/")).status_code == 200
    assert client.post(url(order, "cancel/")).status_code == 409
    product.refresh_from_db()
    assert product.stock_quantity == 10 and StockMovement.objects.filter(reason="return").count() == 1


# --- guest tracking ----------------------------------------------------------------------------------------------------------------------------


def test_a_guest_tracks_an_order_with_number_and_phone(api_client):
    order = new_order(email="guest@example.com")
    r = api_client.post(TRACK, {"order_number": order.number, "phone": "01712345678"}, format="json")
    assert r.status_code == 200
    body = r.json()
    assert body["number"] == order.number and body["status"] == "pending" and body["items"] and "email" not in body
    for hidden in ("source", "created_by", "notes", "ip_address"):
        assert hidden not in body


def test_tracking_accepts_number_and_phone_in_any_common_format(api_client):
    order = new_order()
    r = api_client.post(TRACK, {"order_number": f" {order.number.lower()} ", "phone": "+880 1712-345678"}, format="json")
    assert r.status_code == 200


def test_a_wrong_phone_and_a_wrong_number_look_identical(api_client):
    order = new_order()
    wrong_phone = api_client.post(TRACK, {"order_number": order.number, "phone": "01799999999"}, format="json")
    wrong_number = api_client.post(TRACK, {"order_number": "GP-000000-AAAA", "phone": "01712345678"}, format="json")
    assert wrong_phone.status_code == wrong_number.status_code == 404
    assert wrong_phone.json() == wrong_number.json()


def test_tracking_needs_both_fields_and_a_valid_phone(api_client):
    order = new_order()
    assert api_client.post(TRACK, {"order_number": order.number}, format="json").status_code == 400
    assert api_client.post(TRACK, {"phone": "01712345678"}, format="json").status_code == 400
    assert api_client.post(TRACK, {"order_number": order.number, "phone": "123"}, format="json").status_code == 400


def test_tracking_is_post_only_so_the_phone_stays_out_of_urls(api_client):
    assert api_client.get(TRACK).status_code == 405


def test_tracking_shows_the_courier_details_once_shipped(api_client, admin_user):
    order = new_order()
    Order.objects.filter(pk=order.pk).update(status="processing")
    services.change_status(order, "shipped", user=admin_user, courier={"courier_name": "Steadfast", "tracking_id": "SF123"})
    body = api_client.post(TRACK, {"order_number": order.number, "phone": "01712345678"}, format="json").json()
    assert (body["status"], body["courier_name"], body["tracking_id"]) == ("shipped", "Steadfast", "SF123")
    assert [h["status"] for h in body["history"]] == ["pending", "shipped"]


def test_tracking_is_throttled_per_ip(api_client, settings):
    settings.ORDER_TRACK_THROTTLE_RATE = "3/hour"
    order = new_order()
    data = {"order_number": order.number, "phone": "01712345678"}
    assert [api_client.post(TRACK, data, format="json").status_code for _ in range(4)] == [200, 200, 200, 429]


def test_a_deleted_order_cannot_be_tracked(api_client, admin_user):
    order = new_order()
    services.change_status(order, "cancelled", user=admin_user)
    services.delete_order(order)
    assert api_client.post(TRACK, {"order_number": order.number, "phone": "01712345678"}, format="json").status_code == 404


def test_end_to_end_checkout_then_track(api_client, product):
    number = place(api_client, product).json()["order"]["number"]
    api_client.credentials()
    assert api_client.post(TRACK, {"order_number": number, "phone": "01712345678"}, format="json").json()["number"] == number
