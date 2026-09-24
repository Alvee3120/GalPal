import pytest
from django.test import override_settings

from apps.catalog import services
from apps.catalog.models import StockNotification
from apps.core.messaging import LocMemSMSBackend

from .factories import ProductFactory

pytestmark = pytest.mark.django_db
URL = "/api/v1/stock-notifications/"
SMS = override_settings(SMS_BACKEND="apps.core.messaging.LocMemSMSBackend")


@pytest.fixture(autouse=True)
def clear_outbox():
    LocMemSMSBackend.outbox.clear()


def sold_out(**kwargs):
    return ProductFactory(status="published", manage_stock=True, stock_quantity=0, stock_status="out_of_stock", **kwargs)


def test_a_guest_subscribes_with_a_phone(api_client):
    product = sold_out()
    r = api_client.post(URL, {"product_id": product.id, "phone": "+8801712345678"}, format="json")
    assert r.status_code == 201
    assert StockNotification.objects.get().phone == "01712345678"


def test_a_guest_must_give_a_valid_phone(api_client):
    product = sold_out()
    assert api_client.post(URL, {"product_id": product.id}, format="json").status_code == 400
    assert api_client.post(URL, {"product_id": product.id, "phone": "123"}, format="json").status_code == 400


def test_a_logged_in_customer_uses_their_account_phone(auth_client, customer):
    product = sold_out()
    r = auth_client(customer).post(URL, {"product_id": product.id}, format="json")
    assert r.status_code == 201
    row = StockNotification.objects.get()
    assert row.phone == customer.phone and row.user == customer


def test_asking_twice_is_a_409(api_client):
    product = sold_out()
    body = {"product_id": product.id, "phone": "01712345678"}
    api_client.post(URL, body, format="json")
    r = api_client.post(URL, body, format="json")
    assert r.status_code == 409 and r.json()["error"]["code"] == "already_subscribed"


def test_an_in_stock_or_unpublished_product_is_refused(api_client):
    in_stock = ProductFactory(status="published", manage_stock=True, stock_quantity=5)
    draft = ProductFactory(status="draft", manage_stock=True, stock_quantity=0)
    for product in (in_stock, draft):
        assert api_client.post(URL, {"product_id": product.id, "phone": "01712345678"}, format="json").status_code == 400


@SMS
def test_restocking_texts_everyone_waiting_once(api_client, django_capture_on_commit_callbacks):
    product = sold_out()
    for phone in ("01712345678", "01812345678"):
        api_client.post(URL, {"product_id": product.id, "phone": phone}, format="json")
    assert LocMemSMSBackend.outbox == []
    with django_capture_on_commit_callbacks(execute=True):
        services.adjust_stock(product=product, quantity_change=5, reason="restock")
    assert sorted(m["to"] for m in LocMemSMSBackend.outbox) == ["01712345678", "01812345678"]
    assert not StockNotification.objects.filter(notified_at__isnull=True).exists()
    with django_capture_on_commit_callbacks(execute=True):
        services.adjust_stock(product=product, quantity_change=5, reason="restock")  # already in stock: no repeat
    assert len(LocMemSMSBackend.outbox) == 2


ADMIN_URL = "/api/v1/admin/stock-notifications/"


def test_staff_see_who_is_waiting(auth_client, cce_user, customer, api_client):
    product = sold_out(name="Rose Serum")
    api_client.post(URL, {"product_id": product.id, "phone": "01812345678"}, format="json")
    auth_client(customer).post(URL, {"product_id": product.id}, format="json")
    body = auth_client(cce_user).get(f"{ADMIN_URL}?status=waiting&search=rose").json()
    assert body["count"] == 2
    row = next(r for r in body["results"] if r["phone"] == customer.phone)
    assert row["customer_name"] == customer.full_name and row["status"] == "waiting" and row["in_stock_now"] is False
    assert row["product"]["name"] == "Rose Serum" and row["variant"] is None
    assert auth_client(cce_user).get(f"{ADMIN_URL}?status=notified").json()["count"] == 0


def test_customers_cannot_see_the_list(auth_client, customer):
    assert auth_client(customer).get(ADMIN_URL).status_code == 403


def test_staff_can_mark_a_request_notified_and_back(auth_client, cce_user, api_client):
    product = sold_out()
    created = api_client.post(URL, {"product_id": product.id, "phone": "01712345678"}, format="json").json()
    client = auth_client(cce_user)
    url = f"{ADMIN_URL}{created['id']}/"
    r = client.patch(url, {"status": "notified"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "notified" and r.json()["notified_at"]
    r = client.patch(url, {"status": "waiting"}, format="json")
    assert r.json()["status"] == "waiting" and r.json()["notified_at"] is None
    assert client.patch(url, {"status": "sent"}, format="json").status_code == 400
