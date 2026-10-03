"""Module 18 — audit log, throttles, security headers."""

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.audit.services import diff, redact
from apps.orders.models import Order
from apps.orders.tests.helpers import new_order

pytestmark = pytest.mark.django_db

A = "/api/v1/admin/audit-logs/"


def test_audit_log_is_admin_only(api_client, auth_client, cce_user, customer):
    assert api_client.get(A).status_code == 401
    assert auth_client(cce_user).get(A).status_code == 403
    assert auth_client(customer).get(A).status_code == 403


def test_staff_write_is_logged_with_ip_and_redacted_body(auth_client, cce_user):
    order = new_order(staff=cce_user)
    r = auth_client(cce_user).post(f"/api/v1/admin/orders/{order.pk}/notes/", {"text": "Called", "password": "x"}, format="json", REMOTE_ADDR="203.0.113.7")
    assert r.status_code == 201
    request_entry = AuditLog.objects.get(action="api.post", path__endswith="/notes/")
    assert request_entry.actor == cce_user and request_entry.ip_address == "203.0.113.7" and request_entry.status_code == 201
    assert request_entry.metadata["body"]["password"] == "[redacted]"
    assert AuditLog.objects.filter(action="order.note_added", target_id=str(order.pk)).exists()


def test_manual_order_and_status_change_events(auth_client, cce_user, admin_user):
    order = new_order(staff=cce_user)
    created = AuditLog.objects.get(action="order.created", target_id=str(order.pk))
    assert created.metadata["source"] == order.source
    from apps.orders import services

    services.change_status(Order.objects.get(pk=order.pk), "confirmed", user=admin_user)
    entry = AuditLog.objects.get(action="order.status_changed", target_id=str(order.pk))
    assert entry.changes == {"status": ["pending", "confirmed"]} and entry.actor == admin_user


def test_shipping_override_has_before_and_after(admin_user):
    from apps.orders import services

    order = new_order()
    services.override_shipping(order, charge="0", reason="VIP", user=admin_user)
    entry = AuditLog.objects.get(action="order.shipping_override")
    assert Decimal(entry.changes["shipping_charge"][1]) == 0 and entry.metadata["reason"] == "VIP"


def test_reads_and_customer_requests_are_not_logged(auth_client, admin_user, customer):
    auth_client(admin_user).get("/api/v1/admin/orders/")
    auth_client(customer).get("/api/v1/orders/")
    assert not AuditLog.objects.filter(action__startswith="api.").exists()


def test_helpers():
    assert diff({"a": 1, "b": 2}, {"a": 1, "b": 3}) == {"b": [2, 3]}
    assert redact({"new_password": "x", "nested": [{"refresh": "t"}], "name": "Rina"}) == {"new_password": "[redacted]", "nested": [{"refresh": "[redacted]"}], "name": "Rina"}


# --- throttles ------------------------------------------------------------------------------------------------------------


def test_login_is_limited_per_identifier(api_client, settings):
    settings.LOGIN_IDENTIFIER_THROTTLE_RATE = "3/hour"
    body = {"identifier": "01700000000", "password": "wrong-password"}
    codes = [api_client.post("/api/v1/auth/login/", body, format="json").status_code for _ in range(4)]
    assert codes[-1] == 429


def test_password_reset_requests_are_limited(api_client, settings):
    settings.OTP_REQUEST_IDENTIFIER_THROTTLE_RATE = "2/hour"
    body = {"identifier": "someone@example.com"}
    codes = [api_client.post("/api/v1/auth/password/forgot/", body, format="json").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# --- headers --------------------------------------------------------------------------------------------------------------


def test_api_security_headers(api_client, auth_client, admin_user):
    r = api_client.get("/api/v1/health/")
    assert "default-src 'none'" in r["Content-Security-Policy"] and "camera=()" in r["Permissions-Policy"]
    assert auth_client(admin_user).get("/api/v1/admin/orders/")["Cache-Control"] == "no-store"
