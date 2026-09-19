import pytest
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.tests.factories import DEFAULT_PASSWORD, AdminFactory, CCEFactory, UserFactory
from apps.core.messaging import LocMemSMSBackend


@pytest.fixture(autouse=True)
def _clear_outboxes():
    LocMemSMSBackend.outbox.clear()
    mail.outbox.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client():
    """`auth_client(user)` -> APIClient authenticated with a real JWT access token."""

    def make(user):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
        return client

    return make


@pytest.fixture
def password():
    return DEFAULT_PASSWORD


@pytest.fixture
def admin_user(db):
    return AdminFactory()


@pytest.fixture
def cce_user(db):
    return CCEFactory()


@pytest.fixture
def customer(db):
    return UserFactory()
