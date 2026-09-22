import hashlib
import hmac
import json

import pytest

from apps.catalog.tests.factories import ProductFactory
from apps.orders.tests.helpers import new_order
from apps.shipping import seed
from apps.shipping.models import DeliveryMethod, DeliveryZone, District, ShippingChargeHistory, ZoneDistrict

STUB_SECRET = "dev-stub-secret-change-me"


@pytest.fixture(autouse=True)
def shipping_defaults(db):
    """
    Inside Dhaka 70 / Outside Dhaka 120, the way the seed leaves them. Rebuilt per test: the data
    migration seeds this once, but a `transaction=True` test (see test_concurrency.py) flushes the
    database afterward, which wipes it for whichever test runs next in the same session.
    """
    DeliveryZone.objects.all().delete()
    DeliveryMethod.objects.all().delete()
    ShippingChargeHistory.objects.all().delete()
    seed.seed_all(District, DeliveryZone, ZoneDistrict, DeliveryMethod, ShippingChargeHistory)


@pytest.fixture(autouse=True)
def stub_secret(settings):
    settings.PAYMENT_STUB_GATEWAY_SECRET = STUB_SECRET
    settings.PAYMENT_STUB_GATEWAY_BASE_URL = "https://stub-gateway.test/pay"
    settings.DEFAULT_PAYMENT_GATEWAY = "stub"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


@pytest.fixture
def cce_client(auth_client, cce_user):
    return auth_client(cce_user)


@pytest.fixture
def order(admin_user):
    return new_order(admin_user)


@pytest.fixture
def payment(order):
    return order.payment


@pytest.fixture
def product():
    return ProductFactory(regular_price="500.00", stock_quantity=20, manage_stock=True)


def sign(body: bytes) -> str:
    return hmac.new(STUB_SECRET.encode(), body, hashlib.sha256).hexdigest()


def callback_body(reference, status, amount=None):
    payload = {"reference": reference, "status": status}
    if amount is not None:
        payload["amount"] = str(amount)
    return json.dumps(payload).encode()
