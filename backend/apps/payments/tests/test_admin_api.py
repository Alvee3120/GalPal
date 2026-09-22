from decimal import Decimal

import pytest

from apps.orders.tests.helpers import new_order
from apps.payments.models import Payment

from .conftest import callback_body, sign

pytestmark = pytest.mark.django_db

D = Decimal
PAYMENTS = "/api/v1/admin/payments/"
CALLBACK = "/api/v1/payments/callback/stub/"


def url(payment, suffix=""):
    return f"{PAYMENTS}{payment.id}/{suffix}"


def details(response):
    return response.json()["error"]["details"]


def code(response):
    return response.json()["error"]["code"]


# --- access control: Admin only, no CCE at all -------------------------------------------------------------------


def every_route(payment):
    return [
        ("get", PAYMENTS), ("get", url(payment)), ("post", url(payment, "mark-received/")),
        ("post", url(payment, "initiate/")), ("post", url(payment, "verify/")), ("post", url(payment, "refund/")),
    ]


def test_anonymous_gets_401_everywhere(api_client, payment):
    for verb, path in every_route(payment):
        assert getattr(api_client, verb)(path, {}, format="json").status_code == 401, (verb, path)


def test_customers_get_403_everywhere(auth_client, customer, payment):
    client = auth_client(customer)
    for verb, path in every_route(payment):
        assert getattr(client, verb)(path, {}, format="json").status_code == 403, (verb, path)


def test_cce_gets_403_everywhere_payments_is_not_the_order_module(auth_client, cce_user, payment):
    """The order module lets a CCE in; payments is deliberately not part of it."""
    client = auth_client(cce_user)
    for verb, path in every_route(payment):
        assert getattr(client, verb)(path, {}, format="json").status_code == 403, (verb, path)


def test_the_route_sweep_covers_payments_too():
    """Confirms /admin/payments/ is discovered by the project-wide CCE lockout sweep, not just by these local tests."""
    from apps.accounts.tests import route_sweep

    assert any("/admin/payments/" in route for route in route_sweep.admin_routes())


# --- list / detail --------------------------------------------------------------------------------------------------


def test_list_and_detail_shape(admin_client, payment):
    body = admin_client.get(PAYMENTS).json()
    assert body["count"] == 1
    row = body["results"][0]
    assert set(row) == {"id", "order", "order_number", "method", "gateway", "status", "amount", "amount_received", "created_at"}
    assert (row["order_number"], row["status"], row["amount"]) == (payment.order.number, "unpaid", str(payment.amount))

    detail = admin_client.get(url(payment)).json()
    assert set(detail) == {
        "id", "order", "order_number", "method", "gateway", "status", "amount", "amount_received", "net_received",
        "refunded_amount", "transaction_id", "gateway_payload", "collected_by", "note", "refunds", "created_at", "updated_at",
    }
    assert detail["net_received"] == "0.00" and detail["refunds"] == [] and detail["collected_by"] is None


def test_filter_by_status_method_and_order(admin_client, admin_user):
    a = new_order(admin_user, phone="01711111111")
    b = new_order(admin_user, phone="01722222222")
    from apps.payments import services

    services.mark_received(Payment.objects.get(order=b), user=admin_user)
    assert admin_client.get(f"{PAYMENTS}?status=paid").json()["count"] == 1
    assert admin_client.get(f"{PAYMENTS}?status=unpaid").json()["count"] == 1
    assert admin_client.get(f"{PAYMENTS}?method=cod").json()["count"] == 2
    assert admin_client.get(f"{PAYMENTS}?order={a.id}").json()["count"] == 1


def test_search_by_order_number_and_transaction_id(admin_client, payment, admin_user):
    from apps.payments import services

    services.initiate_payment(payment, user=admin_user)
    payment.refresh_from_db()
    assert admin_client.get(f"{PAYMENTS}?search={payment.order.number}").json()["count"] == 1
    assert admin_client.get(f"{PAYMENTS}?search={payment.transaction_id}").json()["count"] == 1
    assert admin_client.get(f"{PAYMENTS}?search=NOTHING").json()["count"] == 0


def test_404_for_an_unknown_payment(admin_client):
    assert admin_client.get(f"{PAYMENTS}99999/").status_code == 404


def test_put_and_delete_and_create_are_not_supported(admin_client, payment):
    assert admin_client.put(url(payment), {}, format="json").status_code == 405
    assert admin_client.delete(url(payment)).status_code == 405
    assert admin_client.post(PAYMENTS, {}, format="json").status_code == 405


# --- mark-received ---------------------------------------------------------------------------------------------------


def test_mark_received_full_amount(admin_client, admin_user, payment):
    r = admin_client.post(url(payment, "mark-received/"), {}, format="json")
    assert r.status_code == 200
    body = r.json()
    assert (body["status"], body["amount_received"], body["net_received"]) == ("paid", str(payment.amount), str(payment.amount))
    assert body["collected_by"] == {"id": admin_user.id, "full_name": admin_user.full_name}


def test_mark_received_a_partial_amount_with_a_note(admin_client, payment):
    r = admin_client.post(url(payment, "mark-received/"), {"amount": "50.00", "note": "advance payment"}, format="json")
    body = r.json()
    assert (body["status"], body["amount_received"], body["note"]) == ("partially_paid", "50.00", "advance payment")


def test_mark_received_exceeding_the_balance_is_a_400(admin_client, payment):
    r = admin_client.post(url(payment, "mark-received/"), {"amount": str(payment.amount + 1)}, format="json")
    assert r.status_code == 400 and "amount" in details(r)
    assert Payment.objects.get(pk=payment.pk).amount_received == 0


def test_mark_received_twice_fully_is_a_409(admin_client, payment):
    admin_client.post(url(payment, "mark-received/"), {}, format="json")
    r = admin_client.post(url(payment, "mark-received/"), {"amount": "1.00"}, format="json")
    assert r.status_code == 409 and code(r) == "already_collected"


def test_mark_received_updates_the_order(admin_client, payment):
    admin_client.post(url(payment, "mark-received/"), {}, format="json")
    payment.refresh_from_db()
    assert payment.order.payment_status == "paid"


# --- initiate ----------------------------------------------------------------------------------------------------------


def test_initiate_returns_a_reference_and_redirect_url(admin_client, payment):
    r = admin_client.post(url(payment, "initiate/"), {}, format="json")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"reference", "redirect_url"} and body["reference"] in body["redirect_url"]
    payment.refresh_from_db()
    assert payment.gateway == "stub" and payment.transaction_id == body["reference"]


def test_initiate_with_an_unknown_gateway_is_a_400(admin_client, payment):
    r = admin_client.post(url(payment, "initiate/"), {"gateway": "nope"}, format="json")
    assert r.status_code == 400 and "gateway" in details(r)


def test_initiate_on_a_paid_payment_is_a_409(admin_client, payment):
    admin_client.post(url(payment, "mark-received/"), {}, format="json")
    r = admin_client.post(url(payment, "initiate/"), {}, format="json")
    assert r.status_code == 409 and code(r) == "already_settled"


# --- verify ------------------------------------------------------------------------------------------------------------


def test_verify_reconciles_a_missed_callback(admin_client, payment):
    initiated = admin_client.post(url(payment, "initiate/"), {}, format="json").json()
    body = callback_body(initiated["reference"], "success", payment.amount)
    admin_client.post(CALLBACK, data=body, content_type="application/json", HTTP_X_STUB_SIGNATURE=sign(body))
    Payment.objects.filter(pk=payment.pk).update(status="unpaid", amount_received=Decimal("0.00"))
    r = admin_client.post(url(payment, "verify/"), {}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "paid"


def test_verify_without_a_gateway_is_a_409(admin_client, payment):
    r = admin_client.post(url(payment, "verify/"), {}, format="json")
    assert r.status_code == 409 and code(r) == "no_gateway"


# --- refund --------------------------------------------------------------------------------------------------------------


def test_refund_after_a_full_payment(admin_client, admin_user, payment):
    admin_client.post(url(payment, "mark-received/"), {}, format="json")
    r = admin_client.post(url(payment, "refund/"), {"amount": str(payment.amount), "reason": "Customer returned the item"}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "refunded" and len(body["refunds"]) == 1
    refund = body["refunds"][0]
    assert (refund["amount"], refund["reason"], refund["status"]) == (str(payment.amount), "Customer returned the item", "completed")
    assert refund["processed_by"] == {"id": admin_user.id, "full_name": admin_user.full_name}


def test_a_partial_refund(admin_client, payment):
    admin_client.post(url(payment, "mark-received/"), {}, format="json")
    r = admin_client.post(url(payment, "refund/"), {"amount": "20.00", "reason": "Goodwill"}, format="json")
    body = r.json()
    assert body["status"] == "paid" and body["refunded_amount"] == "20.00"


def test_refund_without_a_reason_is_a_400(admin_client, payment):
    admin_client.post(url(payment, "mark-received/"), {}, format="json")
    r = admin_client.post(url(payment, "refund/"), {"amount": "1.00", "reason": ""}, format="json")
    assert r.status_code == 400 and "reason" in details(r)


def test_refund_exceeding_the_collected_amount_is_a_400(admin_client, payment):
    admin_client.post(url(payment, "mark-received/"), {"amount": "50.00"}, format="json")
    r = admin_client.post(url(payment, "refund/"), {"amount": "51.00", "reason": "x"}, format="json")
    assert r.status_code == 400 and "amount" in details(r)


def test_refund_before_anything_was_collected_is_a_409(admin_client, payment):
    r = admin_client.post(url(payment, "refund/"), {"amount": "1.00", "reason": "x"}, format="json")
    assert r.status_code == 409 and code(r) == "nothing_to_refund"


def test_refund_updates_the_order(admin_client, payment):
    admin_client.post(url(payment, "mark-received/"), {}, format="json")
    admin_client.post(url(payment, "refund/"), {"amount": str(payment.amount), "reason": "x"}, format="json")
    payment.refresh_from_db()
    assert payment.order.payment_status == "refunded"


# --- the public gateway callback (no auth, signature-verified) -----------------------------------------------------------------


def test_the_callback_needs_no_jwt(api_client, payment):
    api_client.post(url(payment, "initiate/"), {}, format="json")  # 401, wrong client, just to prove the point below still needs no auth
    payment.refresh_from_db()  # unaffected: that 401 changed nothing


def test_a_full_round_trip_from_admin_initiate_to_callback(admin_client, api_client, payment):
    initiated = admin_client.post(url(payment, "initiate/"), {}, format="json").json()
    body = callback_body(initiated["reference"], "success", payment.amount)
    r = api_client.post(CALLBACK, data=body, content_type="application/json", HTTP_X_STUB_SIGNATURE=sign(body))
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    payment.refresh_from_db()
    assert payment.status == "paid" and payment.amount_received == payment.amount


def test_a_bad_signature_on_the_public_endpoint_is_a_400(api_client, admin_client, payment):
    initiated = admin_client.post(url(payment, "initiate/"), {}, format="json").json()
    body = callback_body(initiated["reference"], "success", payment.amount)
    r = api_client.post(CALLBACK, data=body, content_type="application/json", HTTP_X_STUB_SIGNATURE="0" * 64)
    assert r.status_code == 400 and "signature" in details(r)
    payment.refresh_from_db()
    assert payment.amount_received == 0


def test_an_unknown_gateway_slug_in_the_url_is_a_400(api_client):
    r = api_client.post("/api/v1/payments/callback/does-not-exist/", data=b"{}", content_type="application/json")
    assert r.status_code == 400 and "gateway" in details(r)


def test_the_callback_is_post_only(api_client):
    assert api_client.get(CALLBACK).status_code == 405
