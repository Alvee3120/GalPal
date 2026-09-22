from unittest import mock

import pytest
import requests

from apps.marketing.models import TrackingDestination, TrackingEventLog, TrackingEventName
from apps.marketing.tasks import dispatch_purchase_event, send_ga4_event_task, send_meta_event_task
from apps.orders.tests.helpers import new_order

from .conftest import set_site

pytestmark = pytest.mark.django_db


# --- tasks run synchronously in tests (CELERY_TASK_ALWAYS_EAGER) --------------------------------------------------


def test_celery_is_running_tasks_eagerly_in_tests(settings):
    assert settings.CELERY_TASK_ALWAYS_EAGER is True


@mock.patch("requests.post")
def test_send_meta_event_task_resolves_order_and_user_by_id(post, meta_configured, admin_user):
    order = new_order(admin_user)
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    send_meta_event_task.delay(event_name="ViewContent", user_data={}, order_id=order.pk, user_id=admin_user.pk)
    log = TrackingEventLog.objects.get()
    assert log.order == order and log.user == admin_user


def test_send_meta_event_task_tolerates_a_missing_order_or_user_id(meta_configured):
    with mock.patch("requests.post") as post:
        post.return_value = mock.Mock(status_code=200, json=lambda: {})
        send_meta_event_task.delay(event_name="PageView", user_data={}, order_id=999999, user_id=999999)
    log = TrackingEventLog.objects.get()
    assert log.order is None and log.user is None  # a stale/unknown id never crashes the task


@mock.patch("requests.post", side_effect=requests.ConnectionError("x"))
def test_the_task_retries_on_a_connection_error(post, meta_configured):
    """`autoretry_for` + eager mode: the task's own retry raises, since there's no worker to actually retry on."""
    with pytest.raises(Exception):  # noqa: PT011 - Celery wraps/re-raises depending on version; either way it must not swallow it
        send_meta_event_task.apply(kwargs={"event_name": "PageView", "user_data": {}}).get()
    assert TrackingEventLog.objects.filter(success=False).exists()


def test_send_ga4_event_task_runs(ga4_configured):
    with mock.patch("requests.post") as post:
        post.return_value = mock.Mock(status_code=204, json=lambda: {})
        send_ga4_event_task.delay(event_name="Purchase", client_id="1")
    assert TrackingEventLog.objects.filter(destination=TrackingDestination.GA4).exists()


# --- dispatch_purchase_event: the Purchase payload built from a real order -----------------------------------------------


@pytest.fixture
def meta_and_ga4(meta_configured, ga4_configured):
    return meta_configured, ga4_configured


@mock.patch("requests.post")
def test_dispatch_purchase_event_sends_to_both_destinations(post, meta_and_ga4, admin_user):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    order = new_order(admin_user, quantity=2)
    TrackingEventLog.objects.all().delete()  # the checkout signal already fired one; isolate this direct call
    dispatch_purchase_event.delay(order.pk)
    logs = TrackingEventLog.objects.filter(order=order)
    assert {l.destination for l in logs} == {TrackingDestination.META_CAPI, TrackingDestination.GA4}
    assert all(l.event_name == TrackingEventName.PURCHASE for l in logs)


@mock.patch("requests.post")
def test_the_purchase_payload_reflects_the_orders_items_and_total(post, meta_configured, admin_user, product):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    order = new_order(admin_user, product=product, quantity=3)
    dispatch_purchase_event.delay(order.pk)
    log = TrackingEventLog.objects.filter(order=order, destination=TrackingDestination.META_CAPI).latest("id")
    custom = log.request_payload["data"][0]["custom_data"]
    assert custom["value"] == str(order.grand_total) and custom["num_items"] == 3 and product.sku in custom["content_ids"]


@mock.patch("requests.post")
def test_the_purchase_event_id_is_derived_from_the_order_number(post, meta_configured, admin_user):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    order = new_order(admin_user)
    dispatch_purchase_event.delay(order.pk)
    log = TrackingEventLog.objects.filter(order=order, destination=TrackingDestination.META_CAPI).latest("id")
    assert log.event_id == f"order-{order.number}"


# --- the Order signal: automatic firing, and the manual-order toggle ------------------------------------------------------------


@pytest.fixture
def product():
    from apps.catalog.tests.factories import ProductFactory

    return ProductFactory(regular_price="500.00", stock_quantity=20, manage_stock=True)


@mock.patch("requests.post")
def test_a_website_checkout_fires_purchase_automatically(post, meta_configured, api_client, product, django_capture_on_commit_callbacks):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    from apps.orders.tests.helpers import place

    with django_capture_on_commit_callbacks(execute=True):
        place(api_client, product)
    assert TrackingEventLog.objects.filter(event_name=TrackingEventName.PURCHASE).exists()


@mock.patch("requests.post")
def test_a_manual_order_does_not_fire_by_default(post, meta_configured, admin_user, django_capture_on_commit_callbacks):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    with django_capture_on_commit_callbacks(execute=True):
        new_order(admin_user)  # created via create_manual_order -> is_manual=True
    assert not TrackingEventLog.objects.filter(event_name=TrackingEventName.PURCHASE).exists()


@mock.patch("requests.post")
def test_a_manual_order_fires_once_the_toggle_is_on(post, meta_configured, admin_user, django_capture_on_commit_callbacks):
    set_site(send_manual_orders_to_capi=True)
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    with django_capture_on_commit_callbacks(execute=True):
        new_order(admin_user)
    assert TrackingEventLog.objects.filter(event_name=TrackingEventName.PURCHASE).exists()


@mock.patch("requests.post")
def test_nothing_fires_before_the_transaction_commits(post, meta_configured, api_client, product, django_capture_on_commit_callbacks):
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    from apps.orders.tests.helpers import place

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        place(api_client, product)
    assert not TrackingEventLog.objects.filter(event_name=TrackingEventName.PURCHASE).exists()
    assert len(callbacks) >= 1  # queued, not sent


@mock.patch("requests.post")
def test_updating_an_order_afterwards_does_not_refire_purchase(post, meta_configured, admin_user, django_capture_on_commit_callbacks):
    from apps.orders import services as order_services

    set_site(send_manual_orders_to_capi=True)
    post.return_value = mock.Mock(status_code=200, json=lambda: {})
    with django_capture_on_commit_callbacks(execute=True):
        order = new_order(admin_user)
    # one row per destination (meta_capi succeeds, ga4 logs "not configured" here) — never re-fired below
    assert TrackingEventLog.objects.filter(event_name=TrackingEventName.PURCHASE).count() == 2
    with django_capture_on_commit_callbacks(execute=True):
        order_services.update_order(order, user=admin_user, data={"note": "x"})
    assert TrackingEventLog.objects.filter(event_name=TrackingEventName.PURCHASE).count() == 2
