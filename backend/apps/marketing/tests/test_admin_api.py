import pytest

from apps.marketing.models import TrackingDestination, TrackingEventLog, TrackingEventName
from apps.orders.tests.helpers import new_order

pytestmark = pytest.mark.django_db

EVENTS = "/api/v1/admin/tracking-events/"


def make(**kw):
    kw.setdefault("event_name", TrackingEventName.VIEW_CONTENT)
    kw.setdefault("destination", TrackingDestination.META_CAPI)
    kw.setdefault("success", True)
    return TrackingEventLog.objects.create(**kw)


# --- access control --------------------------------------------------------------------------------------------


def test_anonymous_gets_401(api_client):
    log = make()
    assert api_client.get(EVENTS).status_code == 401
    assert api_client.get(f"{EVENTS}{log.id}/").status_code == 401


def test_customers_get_403(auth_client, customer):
    log = make()
    client = auth_client(customer)
    assert client.get(EVENTS).status_code == 403
    assert client.get(f"{EVENTS}{log.id}/").status_code == 403


def test_cce_gets_403(auth_client, cce_user):
    log = make()
    client = auth_client(cce_user)
    assert client.get(EVENTS).status_code == 403
    assert client.get(f"{EVENTS}{log.id}/").status_code == 403


def test_the_route_sweep_covers_tracking_events_too():
    from apps.accounts.tests import route_sweep

    assert any("/admin/tracking-events/" in route for route in route_sweep.admin_routes())


def test_write_methods_are_not_supported(admin_client):
    log = make()
    assert admin_client.post(EVENTS, {}, format="json").status_code == 405
    assert admin_client.patch(f"{EVENTS}{log.id}/", {}, format="json").status_code == 405
    assert admin_client.delete(f"{EVENTS}{log.id}/").status_code == 405


# --- list / detail ---------------------------------------------------------------------------------------------------


def test_list_and_detail_shape(admin_client, admin_user):
    order = new_order(admin_user)
    log = make(event_name=TrackingEventName.PURCHASE, order=order, user=admin_user, success=False, error_message="boom",
               request_payload={"data": [1]}, response_body={"error": "x"}, response_status=400, attempt=2)
    body = admin_client.get(EVENTS).json()
    assert body["count"] == 1
    detail = admin_client.get(f"{EVENTS}{log.id}/").json()
    assert set(detail) == {
        "id", "event_name", "destination", "event_id", "order", "order_number", "user", "is_manual_order",
        "request_payload", "response_status", "response_body", "success", "error_message", "attempt", "created_at",
    }
    assert (detail["order_number"], detail["user"], detail["success"], detail["attempt"]) == (
        order.number, {"id": admin_user.id, "full_name": admin_user.full_name}, False, 2)


def test_filter_by_event_name_destination_success_and_order(admin_client, admin_user):
    order = new_order(admin_user)
    make(event_name=TrackingEventName.PURCHASE, destination=TrackingDestination.GA4, order=order, success=True)
    make(event_name=TrackingEventName.PAGE_VIEW, destination=TrackingDestination.META_CAPI, success=False)
    assert admin_client.get(f"{EVENTS}?event_name=Purchase").json()["count"] == 1
    assert admin_client.get(f"{EVENTS}?destination=ga4").json()["count"] == 1
    assert admin_client.get(f"{EVENTS}?success=false").json()["count"] == 1
    assert admin_client.get(f"{EVENTS}?order={order.id}").json()["count"] == 1


def test_filter_by_manual_order_flag(admin_client):
    make(is_manual_order=True)
    make(is_manual_order=False)
    assert admin_client.get(f"{EVENTS}?is_manual_order=true").json()["count"] == 1


def test_search_by_event_id_and_order_number(admin_client, admin_user):
    order = new_order(admin_user)
    make(event_id="cart-add-99")
    make(order=order)
    assert admin_client.get(f"{EVENTS}?search=cart-add-99").json()["count"] == 1
    assert admin_client.get(f"{EVENTS}?search={order.number}").json()["count"] == 1


def test_newest_first_by_default(admin_client):
    make()
    second = make()
    assert admin_client.get(EVENTS).json()["results"][0]["id"] == second.id


def test_404_for_unknown_id(admin_client):
    assert admin_client.get(f"{EVENTS}99999/").status_code == 404


def test_a_purchase_events_full_send_history_is_visible(admin_client, admin_user):
    """The scenario the spec calls 'for debugging': a failed attempt followed by a successful retry, both kept."""
    order = new_order(admin_user)
    make(event_name=TrackingEventName.PURCHASE, order=order, success=False, error_message="timeout", attempt=1)
    make(event_name=TrackingEventName.PURCHASE, order=order, success=True, attempt=2)
    rows = admin_client.get(f"{EVENTS}?order={order.id}").json()["results"]
    assert len(rows) == 2 and {r["attempt"] for r in rows} == {1, 2}
