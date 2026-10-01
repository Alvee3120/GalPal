"""Old / abandoned carts: items kept in a customer's cart for MORE than 6 hours, for Admin + CCE (read-only)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.cart import old_carts, services
from apps.cart.models import Cart, CartItem
from apps.catalog.tests.factories import ProductFactory

from .factories import CartItemFactory

pytestmark = pytest.mark.django_db

LIST = "/api/v1/admin/orders/old-carts/"


def customer_cart(user=None):
    return Cart.objects.create(user=user or UserFactory(), token=None)


def item(cart, age, **kwargs):
    """A cart line added `age` ago (created_at is auto_now_add, so it's set afterwards)."""
    line = CartItemFactory(cart=cart, **kwargs)
    CartItem.objects.filter(pk=line.pk).update(created_at=timezone.now() - age)
    line.refresh_from_db()
    return line


@pytest.mark.parametrize(("age", "listed"), [
    (timedelta(minutes=1), False),
    (timedelta(hours=5, minutes=59), False),
    (timedelta(hours=6), False),  # exactly 6h is not "more than"
    (timedelta(hours=6, minutes=1), True),
    (timedelta(hours=8), True),
    (timedelta(hours=24), True),
])
def test_only_items_older_than_6_hours_count(age, listed):
    now = timezone.now()
    cart = customer_cart()
    line = CartItemFactory(cart=cart)
    CartItem.objects.filter(pk=line.pk).update(created_at=now - age)
    assert old_carts.old_carts(now=now).filter(pk=cart.pk).exists() is listed


def test_a_customer_with_several_old_items_counts_once():
    cart = customer_cart()
    for _ in range(3):
        item(cart, timedelta(days=3))
    assert old_carts.customers_with_old_carts() == 1 and old_carts.old_carts().count() == 1


def test_a_new_item_doesnt_reset_an_old_one_and_details_show_each_age(auth_client, cce_user):
    cart = customer_cart()
    old = item(cart, timedelta(days=4))
    new = item(cart, timedelta(minutes=5))
    rows = auth_client(cce_user).get(LIST).json()["results"]
    assert [r["id"] for r in rows] == [cart.pk] and rows[0]["line_count"] == 2 and rows[0]["old_line_count"] == 1
    details = auth_client(cce_user).get(f"{LIST}{cart.pk}/").json()
    ages = {i["id"]: i["is_old"] for i in details["items"]}
    assert ages == {old.pk: True, new.pk: False}


def test_removing_the_old_item_or_checking_out_drops_the_cart():
    cart = customer_cart()
    old = item(cart, timedelta(days=3))
    item(cart, timedelta(hours=1))
    services.remove_item(old)
    assert not old_carts.old_carts().exists()
    item(cart, timedelta(days=5))
    cart.items.all().delete()  # what checkout does with the ordered lines
    assert old_carts.customers_with_old_carts() == 0


def test_raising_the_quantity_keeps_the_items_age():
    cart = customer_cart()
    line = item(cart, timedelta(days=3), product=ProductFactory(stock_quantity=20))
    services.set_item_quantity(line, 4)
    assert old_carts.old_carts().filter(pk=cart.pk).exists()


def test_an_out_of_stock_item_stays_and_shows_current_stock(auth_client, admin_user):
    product = ProductFactory(stock_quantity=5, manage_stock=True)
    cart = customer_cart()
    line = item(cart, timedelta(days=3), product=product)
    product.stock_quantity = 0
    product.save()
    details = auth_client(admin_user).get(f"{LIST}{cart.pk}/").json()
    row = details["items"][0]
    assert row["id"] == line.pk and row["in_stock"] is False and row["available_quantity"] == 0
    assert CartItem.objects.filter(pk=line.pk).exists()  # never removed


def test_guest_carts_are_not_listed():
    line = CartItemFactory()  # a guest cart (token, no user)
    CartItem.objects.filter(pk=line.pk).update(created_at=timezone.now() - timedelta(days=5))
    assert not old_carts.old_carts().exists()


def test_search_and_age_filters():
    rina = customer_cart(UserFactory(full_name="Rina Akter"))
    item(rina, timedelta(days=2), product=ProductFactory(name="Vitamin C Serum"))
    karim = customer_cart(UserFactory(full_name="Karim"))
    item(karim, timedelta(days=9))
    assert list(old_carts.old_carts(search="rina")) == [rina]
    assert list(old_carts.old_carts(search="vitamin")) == [rina]
    assert list(old_carts.old_carts(age="1_3")) == [rina]
    assert list(old_carts.old_carts(age="3_plus")) == [karim]
    assert list(old_carts.old_carts(age="6_24")) == []


def test_admin_and_cce_may_read_customers_and_guests_may_not(api_client, auth_client, admin_user, cce_user, customer):
    cart = customer_cart()
    item(cart, timedelta(days=3))
    for user in (admin_user, cce_user):
        r = auth_client(user).get(LIST)
        assert r.status_code == 200 and r.json()["customers_with_old_carts"] == 1
    assert auth_client(customer).get(LIST).status_code == 403
    assert auth_client(customer).get(f"{LIST}{cart.pk}/").status_code == 403
    assert api_client.get(LIST).status_code == 401


def test_logging_in_keeps_when_a_guest_item_was_really_added(customer):
    guest = CartItemFactory()
    added = timezone.now() - timedelta(days=3)
    CartItem.objects.filter(pk=guest.pk).update(created_at=added)
    services.merge_guest_cart_into_user(guest.cart.token, customer)
    moved = CartItem.objects.get(cart__user=customer)
    assert abs((moved.created_at - added).total_seconds()) < 1
