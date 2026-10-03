"""Module 17 — the report breakdowns on the Admin dashboard, and the CSV exports."""

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.orders.models import Order
from apps.orders.tests.helpers import new_order
from apps.reports.exports import safe

pytestmark = pytest.mark.django_db

A = "/api/v1/admin/reports/"


@pytest.mark.parametrize("path", ["export/orders/", "export/products/", "export/customers/"])
def test_reports_are_admin_only(api_client, auth_client, cce_user, customer, path):
    assert api_client.get(A + path).status_code == 401
    assert auth_client(cce_user).get(A + path).status_code == 403
    assert auth_client(customer).get(A + path).status_code == 403


def test_report_breakdowns(auth_client, admin_user, cce_user):
    sale = new_order()
    Order.objects.filter(pk=sale.pk).update(status="confirmed", source="facebook", is_manual=True, created_by=cce_user,
                                             shipping_zone_name="Inside Dhaka", shipping_charge=70, coupon_code="SAVE10", discount_amount=10)
    pending = new_order()
    Order.objects.filter(pk=pending.pk).update(source="website", is_manual=False, created_by=None, shipping_zone_name="Outside Dhaka")
    UserFactory(created_via_checkout=True)

    body = auth_client(admin_user).get("/api/v1/admin/dashboard/").json()["reports"]
    assert body["summary"]["manual_orders"] == 1
    sources = {r["source"]: r for r in body["by_source"]}
    assert sources["facebook"]["sale_orders"] == 1 and sources["website"]["sale_orders"] == 0
    assert body["by_staff"][0]["user_id"] == cce_user.pk and body["by_staff"][0]["orders"] == 1
    zones = {r["zone"]: r for r in body["by_zone"]}
    assert zones["Inside Dhaka"]["shipping_revenue"] in (70, "70.00", 70.0) and zones["Outside Dhaka"]["sale_orders"] == 0
    assert body["coupons"][0]["code"] == "SAVE10"
    assert body["customers"]["new_via_checkout"] >= 1


def test_bad_range_is_400(auth_client, admin_user):
    assert auth_client(admin_user).get(A + "export/orders/?date_from=2026-05-01&date_to=2026-01-01").status_code == 400


def test_orders_csv(auth_client, admin_user):
    order = new_order()
    res = auth_client(admin_user).get(A + "export/orders/")
    assert res.status_code == 200 and res["Content-Type"].startswith("text/csv")
    body = b"".join(res.streaming_content).decode("utf-8-sig")
    assert body.splitlines()[0].startswith("Order number,") and order.number in body


def test_csv_cells_cannot_run_formulas():
    assert safe("=HYPERLINK(\"http://x\")").startswith("'=")
    assert safe("@SUM(A1)") == "'@SUM(A1)" and safe("Rina") == "Rina" and safe(None) == "" and safe(True) == "Yes"
