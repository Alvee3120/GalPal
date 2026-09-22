import hashlib
from decimal import Decimal
from unittest import mock

import pytest
import requests

from apps.accounts.tests.factories import UserFactory
from apps.marketing import services
from apps.marketing.models import TrackingDestination, TrackingEventLog, TrackingEventName

from .conftest import set_site

pytestmark = pytest.mark.django_db


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


# --- hashing / user data --------------------------------------------------------------------------------


def test_email_and_phone_are_hashed_lowercase_and_trimmed():
    data = services.build_user_data(email=" Rina@Example.com ", phone="01712345678")
    assert data["em"] == [sha("rina@example.com")]


def test_the_phone_gets_the_bangladesh_country_code_before_hashing():
    data = services.build_user_data(phone="01712345678")
    assert data["ph"] == [sha("8801712345678")]


def test_name_splits_into_first_and_last():
    data = services.build_user_data(name="Rina Akter")
    assert data["fn"] == [sha("rina")] and data["ln"] == [sha("akter")]


def test_a_single_word_name_has_no_last_name():
    data = services.build_user_data(name="Cher")
    assert data["fn"] == [sha("cher")] and "ln" not in data


def test_blank_fields_are_simply_absent():
    assert services.build_user_data() == {}


def test_fbp_fbc_ip_and_user_agent_are_never_hashed():
    data = services.build_user_data(fbp="fb.1.111", fbc="fb.1.222", client_ip="1.2.3.4", user_agent="Mozilla/5.0")
    assert data == {"fbp": "fb.1.111", "fbc": "fb.1.222", "client_ip_address": "1.2.3.4", "client_user_agent": "Mozilla/5.0"}


def test_explicit_values_win_over_the_user_object():
    user = UserFactory(email="user@example.com", phone="01711111111", full_name="User Name")
    data = services.build_user_data(user=user, email="override@example.com")
    assert data["em"] == [sha("override@example.com")] and data["ph"] == [sha("8801711111111")]


def test_falls_back_to_the_user_object_when_nothing_explicit_is_given():
    user = UserFactory(email="user@example.com", phone="01722222222", full_name="Jane Doe")
    data = services.build_user_data(user=user)
    assert data["em"] == [sha("user@example.com")] and data["fn"] == [sha("jane")]


def test_no_raw_pii_ever_appears_in_the_result():
    data = services.build_user_data(email="secret@example.com", phone="01799999999", name="Secret Name")
    text = str(data)
    assert "secret@example.com" not in text and "01799999999" not in text and "Secret" not in text


# --- send_meta_event -------------------------------------------------------------------------------------------


def test_meta_send_is_skipped_and_logged_when_not_configured():
    log = services.send_meta_event(event_name="ViewContent", user_data={"em": ["x"]})
    assert log.success is False and "not configured" in log.error_message
    assert log.destination == TrackingDestination.META_CAPI


@mock.patch("requests.post")
def test_a_successful_send_is_logged_with_the_response(post, meta_configured):
    post.return_value = mock.Mock(status_code=200, json=lambda: {"events_received": 1})
    log = services.send_meta_event(event_name="ViewContent", event_id="evt-1", user_data={"em": ["x"]})
    assert log.success is True and log.response_status == 200 and log.response_body == {"events_received": 1}
    assert log.event_id == "evt-1" and log.event_name == "ViewContent"


@mock.patch("requests.post")
def test_the_access_token_travels_as_a_query_param_not_in_the_logged_body(post, meta_configured):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    services.send_meta_event(event_name="ViewContent", user_data={})
    kwargs = post.call_args.kwargs
    assert kwargs["params"]["access_token"] == "EAABtest-token-value"
    assert "EAABtest-token-value" not in str(kwargs["json"])


@mock.patch("requests.post")
def test_a_rejection_from_meta_is_logged_as_failed_and_not_raised(post, meta_configured):
    post.return_value = mock.Mock(status_code=400, json=lambda: {"error": {"message": "Invalid parameter"}})
    log = services.send_meta_event(event_name="ViewContent", user_data={})
    assert log.success is False and "Invalid parameter" in log.error_message


@mock.patch("requests.post")
def test_a_200_response_that_still_carries_an_error_body_is_a_failure(post, meta_configured):
    """Meta can return HTTP 200 with an embedded `error` object for some validation problems — the
    status code alone is not enough to call it a success."""
    post.return_value = mock.Mock(status_code=200, json=lambda: {"error": {"message": "Unsupported event"}})
    log = services.send_meta_event(event_name="ViewContent", user_data={})
    assert log.success is False and "Unsupported event" in log.error_message


@mock.patch("requests.post", side_effect=requests.ConnectionError("network unreachable"))
def test_a_network_failure_is_logged_and_reraised_so_celery_can_retry(post, meta_configured):
    with pytest.raises(requests.ConnectionError):
        services.send_meta_event(event_name="ViewContent", user_data={})
    log = TrackingEventLog.objects.get()
    assert log.success is False and "network unreachable" in log.error_message


@mock.patch("requests.post")
def test_the_test_event_code_is_included_when_set(post, meta_configured):
    set_site(meta_capi_test_event_code="TEST12345")
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    services.send_meta_event(event_name="ViewContent", user_data={})
    assert post.call_args.kwargs["json"]["test_event_code"] == "TEST12345"


@mock.patch("requests.post")
def test_custom_data_and_event_source_url_are_included_when_given(post, meta_configured):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    services.send_meta_event(event_name="AddToCart", user_data={}, custom_data={"value": "10.00"}, event_source_url="https://x.test/p/1")
    event = post.call_args.kwargs["json"]["data"][0]
    assert event["custom_data"] == {"value": "10.00"} and event["event_source_url"] == "https://x.test/p/1"


# --- idempotency: a repeat of the same event_id is skipped, not sent twice ---------------------------------------


@mock.patch("requests.post")
def test_a_repeat_event_id_is_skipped_not_resent(post, meta_configured):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    services.send_meta_event(event_name="Purchase", event_id="order-GP-1", user_data={})
    services.send_meta_event(event_name="Purchase", event_id="order-GP-1", user_data={})
    assert post.call_count == 1
    assert TrackingEventLog.objects.filter(success=True).count() == 2  # the real send, and the logged skip


def test_a_previously_failed_event_id_can_still_be_retried(meta_configured):
    with mock.patch("requests.post", side_effect=requests.ConnectionError("x")):
        with pytest.raises(requests.ConnectionError):
            services.send_meta_event(event_name="Purchase", event_id="order-GP-2", user_data={})
    with mock.patch("requests.post") as post:
        post.return_value = mock.Mock(status_code=200, json=lambda: {})
        services.send_meta_event(event_name="Purchase", event_id="order-GP-2", user_data={})
    assert post.call_count == 1


def test_no_event_id_means_no_dedup_skipping(meta_configured):
    with mock.patch("requests.post") as post:
        post.return_value = mock.Mock(status_code=200, json=lambda: {})
        services.send_meta_event(event_name="PageView", user_data={})
        services.send_meta_event(event_name="PageView", user_data={})
    assert post.call_count == 2


def test_dedup_is_scoped_to_the_destination(meta_configured):
    """A success already logged for GA4 under the same event_id/event_name must not block Meta's own send."""
    TrackingEventLog.objects.create(
        event_name="Purchase", event_id="order-GP-9", destination=TrackingDestination.GA4, success=True,
    )
    with mock.patch("requests.post") as post:
        post.return_value = mock.Mock(status_code=200, json=lambda: {})
        services.send_meta_event(event_name="Purchase", event_id="order-GP-9", user_data={})
    assert post.call_count == 1  # actually sent, not skipped over GA4's unrelated success


# --- send_ga4_event -----------------------------------------------------------------------------------------------


def test_ga4_send_is_skipped_and_logged_when_not_configured():
    log = services.send_ga4_event(event_name="Purchase", client_id="1")
    assert log.success is False and "not configured" in log.error_message


@mock.patch("requests.post")
def test_a_ga4_204_no_content_response_is_handled(post, ga4_configured):
    response = mock.Mock(status_code=204)
    response.json.side_effect = ValueError("no content")
    post.return_value = response
    log = services.send_ga4_event(event_name="Purchase", client_id="42", params={"value": 10.0})
    assert log.success is True and log.response_body == {}


@mock.patch("requests.post")
def test_ga4_event_name_is_lowercased_and_purchase_maps_correctly(post, ga4_configured):
    post.return_value = mock.Mock(status_code=204, json=lambda: {})
    services.send_ga4_event(event_name="Purchase", client_id="1")
    assert post.call_args.kwargs["json"]["events"][0]["name"] == "purchase"


@mock.patch("requests.post")
def test_ga4_secret_travels_as_a_query_param(post, ga4_configured):
    post.return_value = mock.Mock(status_code=204, json=lambda: {})
    services.send_ga4_event(event_name="Purchase", client_id="1")
    assert post.call_args.kwargs["params"]["api_secret"] == "secret-value"


@mock.patch("requests.post", side_effect=requests.Timeout("slow"))
def test_a_ga4_timeout_is_logged_and_reraised(post, ga4_configured):
    with pytest.raises(requests.Timeout):
        services.send_ga4_event(event_name="Purchase", client_id="1")
    assert TrackingEventLog.objects.get().success is False
