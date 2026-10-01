"""Wishlist (Module 7): logged-in customers save published products; guests are asked to log in."""

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.cart.models import WishlistItem
from apps.catalog.tests.factories import ProductFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/wishlist/"


def test_guests_must_log_in(api_client):
    assert api_client.get(URL).status_code == 401
    assert api_client.post(URL, {"product_id": ProductFactory().id}, format="json").status_code == 401


def test_add_list_and_remove(auth_client, customer):
    client = auth_client(customer)
    first, second = ProductFactory(), ProductFactory()
    assert client.post(URL, {"product_id": first.id}, format="json").status_code == 201
    r = client.post(URL, {"product_id": second.id}, format="json")
    assert r.status_code == 201 and r.json()["product_ids"] == [second.id, first.id]  # newest first
    assert r.json()["products"][0]["slug"] == second.slug
    r = client.delete(f"{URL}{first.id}/")
    assert r.status_code == 200 and r.json()["product_ids"] == [second.id]


def test_saving_twice_is_a_no_op(auth_client, customer):
    client = auth_client(customer)
    product = ProductFactory()
    client.post(URL, {"product_id": product.id}, format="json")
    again = client.post(URL, {"product_id": product.id}, format="json")
    assert again.status_code == 200 and again.json()["count"] == 1
    assert WishlistItem.objects.filter(user=customer).count() == 1


def test_only_published_products_can_be_saved_or_listed(auth_client, customer):
    client = auth_client(customer)
    draft = ProductFactory(status="draft")
    assert client.post(URL, {"product_id": draft.id}, format="json").status_code == 400
    saved = ProductFactory()
    client.post(URL, {"product_id": saved.id}, format="json")
    saved.status = "archived"
    saved.save()
    assert client.get(URL).json()["count"] == 0  # hidden, not deleted
    assert WishlistItem.objects.filter(user=customer, product=saved).exists()


def test_each_customer_sees_only_their_own(auth_client, customer):
    other = UserFactory()
    WishlistItem.objects.create(user=other, product=ProductFactory())
    assert auth_client(customer).get(URL).json()["count"] == 0


def test_removing_something_not_saved_is_fine(auth_client, customer):
    assert auth_client(customer).delete(f"{URL}999999/").status_code == 200
