import pytest

from apps.catalog.tests.factories import ProductFactory


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


@pytest.fixture
def cce_client(auth_client, cce_user):
    return auth_client(cce_user)


@pytest.fixture
def product():
    return ProductFactory(status="published", stock_quantity=20, manage_stock=True)
