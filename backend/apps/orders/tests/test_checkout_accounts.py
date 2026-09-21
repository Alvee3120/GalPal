"""
Guest "save my details" checkout: account creation, the emailed password, and the promises around it
(nothing revealed about existing accounts, the password never stored/returned/logged, one atomic flow).
"""
import logging
from unittest import mock

import pytest
from django.core import mail

from apps.accounts.models import Address, User
from apps.accounts.tests.factories import UserFactory
from apps.catalog.models import StockMovement
from apps.catalog.tests.factories import ProductFactory
from apps.coupons.models import CouponUsage
from apps.coupons.tests.factories import CouponFactory
from apps.orders.models import Order

from .conftest import set_site
from .helpers import CHECKOUT, add_to_cart, code, details, payload, place

pytestmark = pytest.mark.django_db

EMAIL = "rina@example.com"


@pytest.fixture
def commit(django_capture_on_commit_callbacks):
    """Run the after-commit hooks (the account email) that a rolled-back test transaction would otherwise skip."""
    def run(fn):
        with django_capture_on_commit_callbacks(execute=True):
            return fn()
    return run


def order_and_account():
    return Order.objects.get(), User.objects.filter(email=EMAIL).first()


# --- save_details = false ---------------------------------------------------------------------------------------------------


def test_no_save_details_is_a_pure_guest_order_and_email_is_optional(api_client, product, commit):
    r = commit(lambda: place(api_client, product, save_details=False))
    assert r.status_code == 201 and r.json()["account_created"] is False
    order = Order.objects.get()
    assert order.customer is None and User.objects.filter(created_via_checkout=True).count() == 0 and mail.outbox == []


def test_no_save_details_with_an_email_still_creates_no_account(api_client, product, commit):
    commit(lambda: place(api_client, product, email=EMAIL))
    assert Order.objects.get().email == EMAIL and not User.objects.filter(email=EMAIL).exists() and mail.outbox == []


# --- save_details = true -------------------------------------------------------------------------------------------------------


def test_save_details_creates_a_linked_flagged_account_with_a_default_address(api_client, product, commit):
    r = commit(lambda: place(api_client, product, save_details=True, email=EMAIL, division="Dhaka"))
    assert r.status_code == 201 and r.json()["account_created"] is True
    order, user = order_and_account()
    assert order.customer == user and user.phone == "01712345678" and user.full_name == "Rina Akter"
    assert user.created_via_checkout is True and user.must_change_password is True and user.role == "customer"
    address = Address.objects.get(user=user)
    assert address.is_default and (address.district, address.area, address.address_line, address.division) == ("Dhaka", "Mirpur", "House 4, Road 2", "Dhaka")
    assert (address.full_name, address.phone) == ("Rina Akter", "01712345678")


def test_the_generated_password_is_emailed_after_commit_and_works(api_client, product, commit):
    commit(lambda: place(api_client, product, save_details=True, email=EMAIL))
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [EMAIL] and "account details" in message.subject.lower()
    password = next(line.split("Password:")[1].strip() for line in message.body.splitlines() if "Password:" in line)
    user = User.objects.get(email=EMAIL)
    assert len(password) >= 12 and user.check_password(password)
    assert "01712345678" in message.body and "change" in message.body.lower()  # login identifier + change prompt


def test_no_email_is_sent_before_the_transaction_commits(api_client, product, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        place(api_client, product, save_details=True, email=EMAIL)
    assert mail.outbox == [] and len(callbacks) >= 1  # queued, not sent


def test_the_password_never_appears_in_the_response(api_client, product, commit):
    r = commit(lambda: place(api_client, product, save_details=True, email=EMAIL))
    password = next(line.split("Password:")[1].strip() for line in mail.outbox[0].body.splitlines() if "Password:" in line)
    assert password not in r.content.decode()
    assert "password" not in r.content.decode().lower() and "token" not in r.content.decode().lower()


def test_only_a_hash_is_stored(api_client, product, commit):
    commit(lambda: place(api_client, product, save_details=True, email=EMAIL))
    password = next(line.split("Password:")[1].strip() for line in mail.outbox[0].body.splitlines() if "Password:" in line)
    user = User.objects.get(email=EMAIL)
    assert user.password != password and user.password.startswith(("pbkdf2_", "md5$", "argon2"))
    from django.db import connection

    with connection.cursor() as cursor:  # and it is in no column of the order or the user
        cursor.execute("SELECT count(*) FROM orders_order WHERE row_to_json(orders_order)::text LIKE %s", [f"%{password}%"])
        assert cursor.fetchone()[0] == 0


def test_the_password_is_never_logged(api_client, product, commit, caplog):
    with caplog.at_level(logging.DEBUG):
        commit(lambda: place(api_client, product, save_details=True, email=EMAIL))
    password = next(line.split("Password:")[1].strip() for line in mail.outbox[0].body.splitlines() if "Password:" in line)
    assert password not in caplog.text


def test_save_details_without_an_email_is_a_validation_error_on_email(api_client, product):
    r = place(api_client, product, save_details=True, email="")
    assert r.status_code == 400 and "email" in details(r) and Order.objects.count() == 0


def test_save_details_with_an_invalid_email_is_a_validation_error_on_email(api_client, product):
    r = place(api_client, product, save_details=True, email="not-an-email")
    assert r.status_code == 400 and "email" in details(r) and Order.objects.count() == 0


def test_when_the_store_disallows_it_save_details_is_treated_as_false(api_client, product, commit):
    set_site(allow_checkout_account_creation=False)
    r = commit(lambda: place(api_client, product, save_details=True, email=""))  # no email needed either
    assert r.status_code == 201 and r.json()["account_created"] is False
    assert Order.objects.get().customer is None and User.objects.filter(created_via_checkout=True).count() == 0 and mail.outbox == []


def test_a_logged_in_customer_never_gets_a_second_account(auth_client, customer, product, commit):
    r = commit(lambda: place(auth_client(customer), product, save_details=True, email=EMAIL))
    assert r.json()["account_created"] is False and User.objects.filter(email=EMAIL).count() == 0
    assert Order.objects.get().customer == customer and mail.outbox == []


# --- an account already exists: never duplicate, attach or reveal ------------------------------------------------------------------


def shape(response):
    body = response.json()
    return response.status_code, set(body), set(body["order"]), body["account_created"]


def test_an_existing_phone_gets_a_normal_guest_order_and_nothing_is_revealed(api_client, product, commit):
    UserFactory(phone="01712345678", email="someone.else@example.com")
    before = User.objects.count()
    r = commit(lambda: place(api_client, product, save_details=True, email=EMAIL))
    assert (r.status_code, r.json()["account_created"]) == (201, False)
    order = Order.objects.get()
    assert order.customer is None and User.objects.count() == before and mail.outbox == []
    assert "exist" not in r.content.decode().lower() and "already" not in r.content.decode().lower()


def test_an_existing_email_gets_a_normal_guest_order_and_nothing_is_revealed(api_client, product, commit):
    UserFactory(phone="01799999999", email=EMAIL)
    before = User.objects.count()
    r = commit(lambda: place(api_client, product, save_details=True, email=EMAIL))
    assert (r.status_code, r.json()["account_created"]) == (201, False)
    assert Order.objects.get().customer is None and User.objects.count() == before and mail.outbox == []


def test_the_response_is_identical_in_shape_whether_or_not_an_account_exists(api_client, commit):
    fresh = commit(lambda: place(api_client, ProductFactory(stock_quantity=5), save_details=True, email=EMAIL, phone="01711111111"))
    api_client.credentials()
    UserFactory(phone="01722222222", email="x@example.com")
    existing = commit(lambda: place(api_client, ProductFactory(stock_quantity=5), save_details=True, email="y@example.com", phone="01722222222"))
    assert shape(fresh)[:3] == shape(existing)[:3] and shape(fresh)[3] is True and shape(existing)[3] is False


def test_a_staff_members_phone_is_treated_like_any_existing_account(api_client, product, admin_user, commit):
    admin_user.phone = "01712345678"
    admin_user.save()
    r = commit(lambda: place(api_client, product, save_details=True, email=EMAIL))
    assert r.json()["account_created"] is False and Order.objects.get().customer is None


# --- failure handling ------------------------------------------------------------------------------------------------------------------


def test_a_failing_email_does_not_fail_the_order(api_client, product, commit, caplog):
    with mock.patch("apps.orders.notifications.send_mail", side_effect=OSError("smtp down")):
        r = commit(lambda: place(api_client, product, save_details=True, email=EMAIL))
    assert r.status_code == 201 and r.json()["account_created"] is True
    order, user = order_and_account()
    assert order.customer == user  # order and account both stand; the customer can use "forgot password"
    assert "Could not send the new-account email" in caplog.text


def test_a_failing_email_never_logs_the_password(api_client, product, commit, caplog):
    seen = {}

    def boom(subject, body, *args, **kwargs):
        seen["body"] = body
        raise OSError("smtp down")

    with mock.patch("apps.orders.notifications.send_mail", side_effect=boom):
        commit(lambda: place(api_client, product, save_details=True, email=EMAIL))
    password = next(line.split("Password:")[1].strip() for line in seen["body"].splitlines() if "Password:" in line)
    assert password not in caplog.text


def test_an_unexpected_account_failure_rolls_back_the_whole_order(api_client, commit):
    product = ProductFactory(stock_quantity=10)
    CouponFactory(code="SAVE50", amount="50.00")
    add_to_cart(api_client, product, quantity=2)
    with mock.patch("apps.orders.services.create_customer_account", side_effect=RuntimeError("db exploded")):
        r = commit(lambda: api_client.post(CHECKOUT, payload(save_details=True, email=EMAIL, coupon="SAVE50"), format="json"))
    assert r.status_code == 500 and "db exploded" not in r.content.decode()  # a clean error, no internals
    product.refresh_from_db()
    assert Order.objects.count() == 0 and User.objects.filter(email=EMAIL).count() == 0
    assert product.stock_quantity == 10 and StockMovement.objects.count() == 0 and CouponUsage.objects.count() == 0
    assert mail.outbox == []  # nothing was committed, so nothing was sent


def test_a_failed_order_sends_no_email_and_creates_no_account(api_client, commit):
    product = ProductFactory(stock_quantity=1)
    add_to_cart(api_client, product)
    product.stock_quantity = 0
    product.save()
    r = commit(lambda: api_client.post(CHECKOUT, payload(save_details=True, email=EMAIL), format="json"))
    assert r.status_code == 400 and mail.outbox == [] and not User.objects.filter(email=EMAIL).exists()


def test_the_cart_is_only_emptied_when_the_whole_flow_succeeds(api_client):
    product = ProductFactory(stock_quantity=10)
    add_to_cart(api_client, product)
    with mock.patch("apps.orders.services.create_customer_account", side_effect=RuntimeError("boom")):
        assert api_client.post(CHECKOUT, payload(save_details=True, email=EMAIL), format="json").status_code == 500
    from apps.cart.models import Cart

    assert Cart.objects.get().items.count() == 1


# --- staff orders never create accounts (the storefront-only rule) ------------------------------------------------------------------


def test_manual_orders_never_create_accounts(auth_client, cce_user, product, commit):
    r = commit(lambda: auth_client(cce_user).post("/api/v1/admin/orders/", {
        "name": "Rina", "phone": "01712345678", "email": EMAIL, "district": "Dhaka", "address_line": "H1", "source": "call",
        "items": [{"product_id": product.id, "quantity": 1}], "save_details": True}, format="json"))
    assert r.status_code == 201 and Order.objects.get().customer is None
    assert not User.objects.filter(email=EMAIL).exists() and mail.outbox == []
