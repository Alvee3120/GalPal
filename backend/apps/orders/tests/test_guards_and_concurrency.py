import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from rest_framework.exceptions import Throttled

from apps.cart.models import Cart, CartItem
from apps.catalog.exceptions import Conflict
from apps.catalog.models import StockMovement
from apps.catalog.tests.factories import ProductFactory
from apps.coupons.models import CouponUsage
from apps.coupons.tests.factories import CouponFactory
from apps.orders import services
from apps.orders.models import Order

from .helpers import CHECKOUT, add_to_cart, code, payload, place

pytestmark = pytest.mark.django_db


# --- duplicate / fake order guards -----------------------------------------------------------------------------------


def test_the_same_phone_and_items_twice_in_a_row_is_a_409(api_client, product):
    assert place(api_client, product).status_code == 201
    r = place(api_client, product)  # the cart is emptied after the first order; refill and resubmit
    assert r.status_code == 409 and code(r) == "duplicate_order" and Order.objects.count() == 1
    assert "GP-" not in r.content.decode()  # the earlier order's number is not handed to whoever resubmits


def test_different_items_from_the_same_phone_are_fine(api_client, product):
    place(api_client, product)
    assert place(api_client, ProductFactory(stock_quantity=5)).status_code == 201


def test_a_different_quantity_is_a_different_order(api_client, product):
    place(api_client, product, quantity=1)
    assert place(api_client, product, quantity=2).status_code == 201


def test_a_different_phone_is_not_a_duplicate(api_client, product):
    place(api_client, product)
    assert place(api_client, product, phone="01787654321").status_code == 201


def test_the_duplicate_window_expires(api_client, product, settings):
    settings.ORDER_DUPLICATE_WINDOW_SECONDS = 0
    place(api_client, product)
    assert place(api_client, product).status_code == 201


def test_a_cancelled_order_does_not_block_reordering(api_client, product, admin_user):
    place(api_client, product)
    services.change_status(Order.objects.get(), "cancelled", user=admin_user)
    assert place(api_client, product).status_code == 201


def test_a_phone_is_capped_per_hour(api_client, settings):
    settings.ORDER_MAX_PER_PHONE_PER_HOUR = 2
    for _ in range(2):
        assert place(api_client, ProductFactory(stock_quantity=5)).status_code == 201
    r = place(api_client, ProductFactory(stock_quantity=5))
    assert r.status_code == 429 and Order.objects.count() == 2


def test_the_hourly_cap_is_per_phone(api_client, settings):
    settings.ORDER_MAX_PER_PHONE_PER_HOUR = 1
    place(api_client, ProductFactory(stock_quantity=5))
    assert place(api_client, ProductFactory(stock_quantity=5), phone="01787654321").status_code == 201


def test_a_client_ip_is_throttled(api_client, settings):
    settings.CHECKOUT_THROTTLE_RATE = "2/hour"
    for i in range(2):
        assert place(api_client, ProductFactory(stock_quantity=5), phone=f"0171234567{i}").status_code == 201
    assert place(api_client, ProductFactory(stock_quantity=5), phone="01787654321").status_code == 429


def test_a_throttled_request_does_not_consume_stock(api_client, settings):
    settings.CHECKOUT_THROTTLE_RATE = "1/hour"
    place(api_client, ProductFactory(stock_quantity=5))
    p = ProductFactory(stock_quantity=5)
    assert place(api_client, p, phone="01787654321").status_code == 429
    p.refresh_from_db()
    assert p.stock_quantity == 5


# --- concurrency: real threads, real transactions -----------------------------------------------------------------------


def make_cart(*products_and_qty):
    cart = Cart.objects.create(token=Cart.new_token())
    for product, quantity in products_and_qty:
        CartItem.objects.create(cart=cart, product=product, quantity=quantity)
    return cart


def data(phone, **extra):
    return {"name": "T", "phone": phone, "district": "Dhaka", "address_line": "x", "payment_method": "cod", **extra}


def run_together(jobs):
    barrier = threading.Barrier(len(jobs))

    def wrap(job):
        try:
            barrier.wait(timeout=10)
            return job()
        except Exception as exc:  # noqa: BLE001 - inspected by the test
            return exc
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(wrap, jobs))


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_cannot_oversell_the_last_units():
    product = ProductFactory(stock_quantity=3, manage_stock=True)
    carts = [make_cart((product, 1)) for _ in range(8)]
    jobs = [lambda c=c, i=i: services.checkout(cart=c, user=None, data=data(f"0171000000{i}")) for i, c in enumerate(carts)]
    results = run_together(jobs)
    ok = [r for r in results if not isinstance(r, Exception)]
    assert len(ok) == 3 and all(isinstance(r, ValidationError) for r in results if isinstance(r, Exception)), results
    product.refresh_from_db()
    assert product.stock_quantity == 0 and Order.objects.count() == 3
    assert sum(-m.quantity_change for m in StockMovement.objects.all()) == 3  # the ledger agrees with the shelf


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_cannot_exceed_a_coupons_total_limit():
    product = ProductFactory(stock_quantity=50, regular_price="500.00")
    coupon = CouponFactory(code="LIMITED", amount="50.00", total_usage_limit=2)
    carts = [make_cart((product, 1)) for _ in range(6)]
    jobs = [lambda c=c, i=i: services.checkout(cart=c, user=None, data=data(f"0172000000{i}", coupon="LIMITED")) for i, c in enumerate(carts)]
    results = run_together(jobs)
    assert len([r for r in results if not isinstance(r, Exception)]) == 2, results
    assert CouponUsage.objects.filter(coupon=coupon).count() == 2 and Order.objects.count() == 2
    product.refresh_from_db()
    assert product.stock_quantity == 48  # the rejected orders took no stock


@pytest.mark.django_db(transaction=True)
def test_simultaneous_identical_submissions_create_exactly_one_order():
    product = ProductFactory(stock_quantity=20)
    carts = [make_cart((product, 1)) for _ in range(5)]
    jobs = [lambda c=c: services.checkout(cart=c, user=None, data=data("01733333333")) for c in carts]
    results = run_together(jobs)
    assert len([r for r in results if not isinstance(r, Exception)]) == 1, results
    assert all(isinstance(r, Conflict) for r in results if isinstance(r, Exception))
    product.refresh_from_db()
    assert Order.objects.count() == 1 and product.stock_quantity == 19


@pytest.mark.django_db(transaction=True)
def test_the_hourly_phone_cap_holds_under_concurrency(settings):
    settings.ORDER_MAX_PER_PHONE_PER_HOUR = 2
    carts = [make_cart((ProductFactory(stock_quantity=5), 1)) for _ in range(6)]
    jobs = [lambda c=c: services.checkout(cart=c, user=None, data=data("01744444444")) for c in carts]
    results = run_together(jobs)
    assert len([r for r in results if not isinstance(r, Exception)]) == 2, results
    assert all(isinstance(r, Throttled) for r in results if isinstance(r, Exception))


@pytest.mark.django_db(transaction=True)
def test_orders_with_the_same_items_in_opposite_order_do_not_deadlock():
    a, b = ProductFactory(stock_quantity=20), ProductFactory(stock_quantity=20)
    cart_one = make_cart((a, 1), (b, 1))
    cart_two = make_cart((b, 1), (a, 1))
    results = run_together([
        lambda: services.checkout(cart=cart_one, user=None, data=data("01755555551")),
        lambda: services.checkout(cart=cart_two, user=None, data=data("01755555552")),
    ])
    assert not [r for r in results if isinstance(r, Exception)], results
    a.refresh_from_db()
    b.refresh_from_db()
    assert (a.stock_quantity, b.stock_quantity) == (18, 18)


@pytest.mark.django_db(transaction=True)
def test_cancelling_twice_at_once_restores_stock_exactly_once(admin_user):
    product = ProductFactory(stock_quantity=10)
    order = services.checkout(cart=make_cart((product, 4)), user=None, data=data("01766666666")).order
    results = run_together([lambda: services.change_status(order, "cancelled", user=admin_user) for _ in range(4)])
    assert len([r for r in results if not isinstance(r, Exception)]) == 1, results
    product.refresh_from_db()
    assert product.stock_quantity == 10 and StockMovement.objects.filter(reason="return").count() == 1


@pytest.mark.django_db(transaction=True)
def test_cancel_and_ship_racing_leave_one_consistent_outcome(admin_user):
    product = ProductFactory(stock_quantity=10)
    order = services.checkout(cart=make_cart((product, 2)), user=None, data=data("01777777777")).order
    services.change_status(order, "confirmed", user=admin_user)
    services.change_status(order, "processing", user=admin_user)
    results = run_together([
        lambda: services.change_status(order, "cancelled", user=admin_user),
        lambda: services.change_status(order, "shipped", user=admin_user),
    ])
    assert len([r for r in results if not isinstance(r, Exception)]) == 1, results
    order.refresh_from_db()
    product.refresh_from_db()
    # cancelled => stock came back; shipped => it stayed out. Never "shipped but stock restored".
    assert (order.status, product.stock_quantity) in {("cancelled", 10), ("shipped", 8)}
