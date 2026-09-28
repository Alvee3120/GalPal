"""Who can open an order's invoice: its customer, a guest with the order's phone, and staff (see test_admin_api)."""

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.orders.models import Order

from .helpers import new_order

pytestmark = pytest.mark.django_db


def owned_by(user, **overrides):
    order = new_order(**overrides)
    Order.objects.filter(pk=order.pk).update(customer=user)
    return order


def test_customers_see_only_their_own_invoice(auth_client, customer):
    mine = owned_by(customer)
    other = owned_by(UserFactory(), phone="01787654321")
    client = auth_client(customer)
    assert client.get(f"/api/v1/orders/{mine.number}/invoice/").json()["order_number"] == mine.number
    assert client.get(f"/api/v1/orders/{other.number}/invoice/").status_code == 404
    pdf = client.get(f"/api/v1/orders/{mine.number}/invoice/pdf/")
    assert pdf.status_code == 200 and pdf["Content-Type"] == "application/pdf" and pdf.content.startswith(b"%PDF")


def test_an_anonymous_visitor_cannot_open_an_invoice_by_number(api_client):
    order = new_order()
    assert api_client.get(f"/api/v1/orders/{order.number}/invoice/").status_code == 401


def test_a_guest_opens_an_invoice_with_the_order_phone(api_client):
    order = new_order()
    body = {"order_number": order.number, "phone": order.phone}
    ok = api_client.post("/api/v1/orders/track/invoice/", body, format="json")
    assert ok.status_code == 200 and ok.json()["order_number"] == order.number
    pdf = api_client.post("/api/v1/orders/track/invoice/pdf/", body, format="json")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    wrong = api_client.post("/api/v1/orders/track/invoice/", {**body, "phone": "01999999999"}, format="json")
    assert wrong.status_code == 404
