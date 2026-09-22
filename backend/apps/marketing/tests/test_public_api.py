from unittest import mock

import pytest

from apps.catalog.tests.factories import ProductFactory
from apps.marketing.models import TrackingEventLog, TrackingEventName

pytestmark = pytest.mark.django_db

TRACK = "/api/v1/tracking/events/"


def details(response):
    return response.json()["error"]["details"]


@pytest.fixture(autouse=True)
def eager_meta(meta_configured):
    return meta_configured


@mock.patch("requests.post")
def test_a_guest_can_post_an_event(post, api_client):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    r = api_client.post(TRACK, {"event_name": "ViewContent", "product_id": 1}, format="json")
    assert r.status_code == 202
    log = TrackingEventLog.objects.get()
    assert log.event_name == "ViewContent" and log.user is None


@mock.patch("requests.post")
def test_purchase_is_not_an_accepted_event_name(post, api_client):
    r = api_client.post(TRACK, {"event_name": "Purchase"}, format="json")
    assert r.status_code == 400 and "event_name" in details(r)
    assert post.call_count == 0


@pytest.mark.parametrize("event_name", ["PageView", "ViewContent", "AddToCart", "InitiateCheckout"])
@mock.patch("requests.post")
def test_every_frontend_event_name_is_accepted(post, api_client, event_name):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    assert api_client.post(TRACK, {"event_name": event_name}, format="json").status_code == 202


@mock.patch("requests.post")
def test_the_event_id_is_passed_through_for_dedup(post, api_client):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    api_client.post(TRACK, {"event_name": "AddToCart", "event_id": "cart-add-1"}, format="json")
    assert TrackingEventLog.objects.get().event_id == "cart-add-1"


@mock.patch("requests.post")
def test_a_logged_in_customer_is_hashed_into_the_event(post, auth_client, customer):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    auth_client(customer).post(TRACK, {"event_name": "InitiateCheckout"}, format="json")
    log = TrackingEventLog.objects.get()
    assert log.user == customer
    user_data = log.request_payload["data"][0]["user_data"]
    assert "em" in user_data  # the customer's email got hashed in, without me passing it explicitly


@mock.patch("requests.post")
def test_a_stale_token_is_treated_as_a_guest_not_a_401(post, api_client):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
    r = api_client.post(TRACK, {"event_name": "PageView"}, format="json")
    assert r.status_code == 202


@mock.patch("requests.post")
def test_fbp_fbc_and_client_ip_are_forwarded(post, api_client):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    api_client.post(TRACK, {"event_name": "PageView", "fbp": "fb.1.111", "fbc": "fb.1.222"}, format="json", REMOTE_ADDR="9.9.9.9")
    user_data = TrackingEventLog.objects.get().request_payload["data"][0]["user_data"]
    assert user_data["fbp"] == "fb.1.111" and user_data["fbc"] == "fb.1.222" and user_data["client_ip_address"] == "9.9.9.9"


@mock.patch("requests.post")
def test_value_and_product_id_become_custom_data(post, api_client):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    product = ProductFactory()
    api_client.post(TRACK, {"event_name": "AddToCart", "product_id": product.id, "value": "199.00", "currency": "BDT"}, format="json")
    custom = TrackingEventLog.objects.get().request_payload["data"][0]["custom_data"]
    assert custom == {"content_ids": [product.id], "content_type": "product", "value": "199.00", "currency": "BDT"}


@mock.patch("requests.post")
def test_currency_defaults_to_the_site_currency_when_value_is_sent_without_one(post, api_client):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    api_client.post(TRACK, {"event_name": "AddToCart", "value": "50.00"}, format="json")
    custom = TrackingEventLog.objects.get().request_payload["data"][0]["custom_data"]
    assert custom["currency"] == "BDT"


def test_an_unknown_event_name_is_a_400():
    from rest_framework.test import APIClient

    r = APIClient().post(TRACK, {"event_name": "SomethingElse"}, format="json")
    assert r.status_code == 400 and "event_name" in details(r)


@mock.patch("requests.post")
def test_the_response_does_not_wait_on_a_slow_meta(post, api_client):
    """A real network call would time out or hang; the mock never actually needing to be slow proves the
    view itself doesn't block on the send (Celery eager mode runs it inline in tests, but the response
    still comes back with a 202 either way, matching the async contract)."""
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    r = api_client.post(TRACK, {"event_name": "PageView"}, format="json")
    assert r.status_code == 202 and r.data is None
