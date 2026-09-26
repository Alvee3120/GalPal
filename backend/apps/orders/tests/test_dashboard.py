from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.tests.factories import ProductFactory
from apps.orders.models import Order

from .helpers import new_order

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/orders/dashboard/"


@pytest.fixture
def cce_client(auth_client, cce_user):
    return auth_client(cce_user)


def test_inventory_counts_and_value(cce_client):
    ProductFactory(status="published", manage_stock=True, stock_quantity=4, regular_price=Decimal("100.00"))  # value 400
    ProductFactory(status="published", manage_stock=True, stock_quantity=0, stock_status="out_of_stock")
    ProductFactory(status="published", manage_stock=False, stock_quantity=0)  # untracked: in stock, no value
    ProductFactory(status="draft", manage_stock=True, stock_quantity=9)  # not on sale: not counted
    inv = cce_client.get(URL).json()["inventory"]
    assert (inv["total_products"], inv["in_stock"], inv["out_of_stock"], inv["untracked_products"]) == (3, 2, 1, 1)
    assert Decimal(inv["inventory_value"]) == Decimal("400.00")


def test_variant_products_use_variant_stock_and_price(cce_client):
    product = ProductFactory(status="published", has_variants=True, manage_stock=True, stock_quantity=0, regular_price=Decimal("50.00"))
    product.variants.create(sku="VA", stock_quantity=2, regular_price=Decimal("80.00"), option_signature="a")  # 160
    product.variants.create(sku="VB", stock_quantity=3, option_signature="b")  # product price: 150
    product.variants.create(sku="VC", stock_quantity=5, is_active=False, option_signature="c")  # inactive: ignored
    inv = cce_client.get(URL).json()["inventory"]
    assert inv["in_stock"] == 1 and Decimal(inv["inventory_value"]) == Decimal("310.00")


def test_sales_count_only_confirmed_orders_that_go_ahead(cce_client, cce_user):
    orders = {status: new_order(cce_user, phone=f"0171000000{i}") for i, status in enumerate(
        ["pending", "confirmed", "delivered", "cancelled", "returned"])}
    for status, order in orders.items():
        Order.objects.filter(pk=order.pk).update(status=status)
    body = cce_client.get(URL).json()
    expected = sum(o.grand_total for s, o in orders.items() if s in ("confirmed", "delivered"))
    assert Decimal(body["sales"]["total"]) == expected and body["sales"]["orders"] == 2
    assert body["orders"]["total"] == 5 and body["orders"]["by_status"]["cancelled"] == 1
    assert sum(day["orders"] for day in body["series"]) == 5 and len(body["series"]) == 30


def test_date_range_and_granularity(cce_client, cce_user):
    order = new_order(cce_user)
    Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(days=60), status="confirmed")
    today = timezone.localdate()
    recent = cce_client.get(URL, {"date_from": today - timedelta(days=6), "date_to": today}).json()
    assert recent["orders"]["total"] == 0 and len(recent["series"]) == 7 and recent["granularity"] == "day"
    year = cce_client.get(URL, {"date_from": today - timedelta(days=364), "date_to": today}).json()
    assert year["orders"]["total"] == 1 and year["granularity"] == "month"
    assert cce_client.get(URL, {"date_from": today, "date_to": today - timedelta(days=1)}).status_code == 400


def test_customers_cannot_see_it(auth_client, customer):
    assert auth_client(customer).get(URL).status_code == 403


ADMIN_URL = "/api/v1/admin/dashboard/"


def test_admin_dashboard_is_admin_only(auth_client, cce_user, customer, admin_user):
    assert auth_client(cce_user).get(ADMIN_URL).status_code == 403
    assert auth_client(customer).get(ADMIN_URL).status_code == 403
    assert auth_client(admin_user).get(ADMIN_URL).status_code == 200


def test_admin_headline_counts_sold_units_and_compares_periods(auth_client, admin_user, cce_user):
    product = ProductFactory(status="published", manage_stock=True, stock_quantity=50)
    today = timezone.localdate()
    now_order = new_order(cce_user, product=product, quantity=3)
    old_order = new_order(cce_user, product=product, quantity=1, phone="01787654321")
    Order.objects.filter(pk=now_order.pk).update(status="delivered")
    Order.objects.filter(pk=old_order.pk).update(status="confirmed", created_at=timezone.now() - timedelta(days=8))
    body = auth_client(admin_user).get(ADMIN_URL, {"date_from": today - timedelta(days=6), "date_to": today}).json()
    head = body["headline"]
    assert head["products_sold"]["value"] == 3 and head["products_sold"]["previous"] == 1
    assert head["products_sold"]["change"] == 200.0 and head["orders"]["change"] == 0.0
    assert body["previous_period"]["date_to"] == (today - timedelta(days=7)).isoformat()
    top = body["top_products"][0]
    assert top["product_id"] == product.id and top["sold"] == 3
    assert body["recent_orders"][0]["id"] == now_order.pk


def test_a_single_day_is_grouped_by_hour(auth_client, admin_user):
    today = timezone.localdate()
    body = auth_client(admin_user).get(ADMIN_URL, {"date_from": today, "date_to": today}).json()
    assert body["granularity"] == "hour" and len(body["series"]) == 24
