from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.exceptions import Conflict
from apps.orders.models import Order
from apps.payments import services
from apps.payments.gateways import GatewayError, GatewayResult, InitiateResult, InvalidSignature
from apps.payments.models import Payment, Refund

from .conftest import callback_body, sign

pytestmark = pytest.mark.django_db

D = Decimal


# --- mark_received --------------------------------------------------------------------------------------


def test_marking_received_without_an_amount_takes_the_full_balance(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    payment.refresh_from_db()
    assert (payment.amount_received, payment.status, payment.collected_by) == (payment.amount, "paid", admin_user)


def test_a_partial_amount_leaves_the_payment_partially_paid(payment, admin_user):
    services.mark_received(payment, amount="200.00", user=admin_user)
    payment.refresh_from_db()
    assert (payment.amount_received, payment.status) == (D("200.00"), "partially_paid")


def test_two_partial_collections_add_up(payment, admin_user):
    services.mark_received(payment, amount="200.00", user=admin_user)
    services.mark_received(payment, amount=str(payment.amount - D("200.00")), user=admin_user)
    payment.refresh_from_db()
    assert (payment.amount_received, payment.status) == (payment.amount, "paid")


def test_a_note_is_recorded(payment, admin_user):
    services.mark_received(payment, note="cash handed to rider", user=admin_user)
    payment.refresh_from_db()
    assert payment.note == "cash handed to rider"


def test_marking_more_than_is_owed_is_refused_and_changes_nothing(payment, admin_user):
    with pytest.raises(ValidationError) as exc:
        services.mark_received(payment, amount=str(payment.amount + 1), user=admin_user)
    assert exc.value.error_dict["amount"][0].code == "exceeds_amount_due"
    payment.refresh_from_db()
    assert payment.amount_received == 0


def test_marking_received_again_once_fully_paid_is_a_409(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    with pytest.raises(Conflict) as exc:
        services.mark_received(payment, amount="1.00", user=admin_user)
    assert exc.value.get_codes() == "already_collected"


@pytest.mark.parametrize("bad", ["-1", "0", "abc", "NaN", "Infinity"])
def test_bad_amounts_are_refused(payment, admin_user, bad):
    with pytest.raises(ValidationError):
        services.mark_received(payment, amount=bad, user=admin_user)
    payment.refresh_from_db()
    assert payment.amount_received == 0


def test_marking_received_syncs_the_order(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    assert Order.objects.get(pk=payment.order_id).payment_status == "paid"


# --- gateway: initiate -----------------------------------------------------------------------------------


def test_initiate_returns_a_redirect_url_and_stamps_the_payment(payment, admin_user):
    updated, result = services.initiate_payment(payment, user=admin_user)
    assert result.reference.startswith("STUB-") and result.redirect_url == f"https://stub-gateway.test/pay/{result.reference}/"
    assert (updated.gateway, updated.transaction_id) == ("stub", result.reference)
    assert updated.gateway_payload["last_initiate"]["amount"] == str(payment.amount)


def test_initiating_twice_gets_two_different_references(payment, admin_user):
    _, first = services.initiate_payment(payment, user=admin_user)
    _, second = services.initiate_payment(payment, user=admin_user)
    assert first.reference != second.reference


def test_an_unknown_gateway_is_a_400(payment, admin_user):
    with pytest.raises(ValidationError) as exc:
        services.initiate_payment(payment, gateway_slug="nonexistent", user=admin_user)
    assert exc.value.error_dict["gateway"][0].code == "unknown_gateway"


def test_a_paid_payment_cannot_be_re_initiated(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    with pytest.raises(Conflict) as exc:
        services.initiate_payment(payment, user=admin_user)
    assert exc.value.get_codes() == "already_settled"


def test_a_partially_paid_or_failed_payment_can_still_be_initiated(payment, admin_user):
    services.mark_received(payment, amount="1.00", user=admin_user)
    services.initiate_payment(payment, user=admin_user)  # no exception


# --- gateway: callback (IPN) -----------------------------------------------------------------------------


def test_a_successful_callback_marks_the_payment_paid(payment, admin_user):
    payment, _ = services.initiate_payment(payment, user=admin_user)
    body = callback_body(payment.transaction_id, "success", payment.amount)
    services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})
    payment.refresh_from_db()
    assert (payment.status, payment.amount_received) == ("paid", payment.amount)
    assert Order.objects.get(pk=payment.order_id).payment_status == "paid"


def test_a_partial_success_amount_is_partially_paid(payment, admin_user):
    payment, _ = services.initiate_payment(payment, user=admin_user)
    half = payment.amount / 2
    body = callback_body(payment.transaction_id, "success", half)
    services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})
    payment.refresh_from_db()
    assert payment.status == "partially_paid" and payment.amount_received == half


def test_a_failed_callback_before_any_success_marks_it_failed(payment, admin_user):
    payment, _ = services.initiate_payment(payment, user=admin_user)
    body = callback_body(payment.transaction_id, "failed")
    services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})
    payment.refresh_from_db()
    assert payment.status == "failed" and payment.amount_received == 0


def test_a_failed_callback_after_a_success_does_not_undo_it(payment, admin_user):
    payment, _ = services.initiate_payment(payment, user=admin_user)
    ok = callback_body(payment.transaction_id, "success", payment.amount)
    services.handle_callback("stub", ok, {"X-Stub-Signature": sign(ok)})
    bad = callback_body(payment.transaction_id, "failed")
    services.handle_callback("stub", bad, {"X-Stub-Signature": sign(bad)})
    payment.refresh_from_db()
    assert payment.status == "paid" and payment.amount_received == payment.amount


def test_a_repeated_success_callback_is_idempotent(payment, admin_user):
    payment, _ = services.initiate_payment(payment, user=admin_user)
    body = callback_body(payment.transaction_id, "success", payment.amount)
    services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})
    services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})  # a webhook retry
    payment.refresh_from_db()
    assert payment.amount_received == payment.amount  # not doubled


def test_a_wrong_signature_is_refused_and_changes_nothing(payment, admin_user):
    payment, _ = services.initiate_payment(payment, user=admin_user)
    body = callback_body(payment.transaction_id, "success", payment.amount)
    with pytest.raises(ValidationError) as exc:
        services.handle_callback("stub", body, {"X-Stub-Signature": "0" * 64})
    assert exc.value.error_dict["signature"][0].code == "invalid_signature"
    payment.refresh_from_db()
    assert payment.amount_received == 0


def test_a_missing_signature_is_refused(payment, admin_user):
    payment, _ = services.initiate_payment(payment, user=admin_user)
    body = callback_body(payment.transaction_id, "success", payment.amount)
    with pytest.raises(ValidationError):
        services.handle_callback("stub", body, {})


@pytest.mark.parametrize("body", [b"not json", b'{"reference": "x"}', b'{"reference": "x", "status": "maybe"}'])
def test_malformed_payloads_are_refused(payment, admin_user, body):
    with pytest.raises(ValidationError) as exc:
        services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})
    assert exc.value.error_dict["payload"][0].code == "malformed_callback"


def test_a_success_with_a_non_positive_amount_is_refused(payment, admin_user):
    payment, _ = services.initiate_payment(payment, user=admin_user)
    body = callback_body(payment.transaction_id, "success", "0")
    with pytest.raises(ValidationError) as exc:
        services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})
    assert exc.value.error_dict["amount"][0].code == "invalid_amount"


def test_an_unknown_reference_is_refused(payment):
    body = callback_body("STUB-DOES-NOT-EXIST", "success", "10.00")
    with pytest.raises(ValidationError) as exc:
        services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})
    assert exc.value.error_dict["reference"][0].code == "unknown_reference"


def test_a_callback_for_an_unknown_gateway_is_refused(payment):
    with pytest.raises(ValidationError) as exc:
        services.handle_callback("does-not-exist", b"{}", {})
    assert exc.value.error_dict["gateway"][0].code == "unknown_gateway"


def test_a_callback_only_matches_its_own_gateway_and_reference_pair(payment, admin_user):
    """A reference that exists but under a different gateway slug must not match."""
    payment, _ = services.initiate_payment(payment, user=admin_user)
    other = Payment.objects.exclude(pk=payment.pk).first()
    if other is None:
        from apps.orders.tests.helpers import new_order

        other = new_order(admin_user, phone="01799999999")
        other = Payment.objects.get(order=other)
    other.transaction_id = payment.transaction_id  # same reference, different row, still gateway=""
    other.save(update_fields=["transaction_id"])
    body = callback_body(payment.transaction_id, "success", "10.00")
    services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})
    other.refresh_from_db()
    assert other.amount_received == 0  # the untouched row (blank gateway) never matched


# --- gateway: verify --------------------------------------------------------------------------------------


def test_verify_replays_the_last_callback(payment, admin_user):
    payment, _ = services.initiate_payment(payment, user=admin_user)
    body = callback_body(payment.transaction_id, "success", payment.amount)
    services.handle_callback("stub", body, {"X-Stub-Signature": sign(body)})
    # Simulate the callback having been missed by the local record: roll status/amount back WITHOUT
    # touching gateway_payload, which is where the gateway's own memory of "what actually happened" lives.
    Payment.objects.filter(pk=payment.pk).update(status="unpaid", amount_received=D("0.00"))
    services.verify_payment(payment, user=admin_user)
    payment.refresh_from_db()
    assert (payment.status, payment.amount_received) == ("paid", payment.amount)


def test_verify_with_no_prior_callback_leaves_the_payment_alone(payment, admin_user):
    services.initiate_payment(payment, user=admin_user)
    services.verify_payment(payment, user=admin_user)
    payment.refresh_from_db()
    assert payment.status == "unpaid" and payment.amount_received == 0


def test_verify_without_a_gateway_is_a_409(payment, admin_user):
    with pytest.raises(Conflict) as exc:
        services.verify_payment(payment, user=admin_user)
    assert exc.value.get_codes() == "no_gateway"


# --- refunds ----------------------------------------------------------------------------------------------


def test_a_full_refund_marks_the_payment_refunded(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    refund = services.create_refund(payment, amount=str(payment.amount), reason="Customer returned the item", user=admin_user)
    payment.refresh_from_db()
    assert (payment.status, refund.status) == ("refunded", "completed")
    assert Order.objects.get(pk=payment.order_id).payment_status == "refunded"


def test_a_partial_refund_keeps_the_payment_paid(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    services.create_refund(payment, amount="10.00", reason="Damaged item, partial goodwill refund", user=admin_user)
    payment.refresh_from_db()
    assert payment.status == "paid" and services.net_received(payment) == payment.amount - D("10.00")


def test_two_refunds_can_add_up_to_a_full_refund(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    half = payment.amount / 2
    services.create_refund(payment, amount=str(half), reason="first half", user=admin_user)
    services.create_refund(payment, amount=str(payment.amount - half), reason="second half", user=admin_user)
    payment.refresh_from_db()
    assert payment.status == "refunded"


def test_refunding_more_than_was_collected_is_refused(payment, admin_user):
    services.mark_received(payment, amount="50.00", user=admin_user)
    with pytest.raises(ValidationError) as exc:
        services.create_refund(payment, amount="51.00", reason="x", user=admin_user)
    assert exc.value.error_dict["amount"][0].code == "exceeds_refundable"
    assert Refund.objects.filter(payment=payment).count() == 0


def test_a_second_refund_is_capped_by_what_is_left(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    services.create_refund(payment, amount=str(payment.amount - D("5.00")), reason="first", user=admin_user)
    with pytest.raises(ValidationError) as exc:
        services.create_refund(payment, amount="6.00", reason="second", user=admin_user)
    assert exc.value.error_dict["amount"][0].code == "exceeds_refundable"


def test_refunding_before_anything_was_collected_is_a_409(payment, admin_user):
    with pytest.raises(Conflict) as exc:
        services.create_refund(payment, amount="1.00", reason="x", user=admin_user)
    assert exc.value.get_codes() == "nothing_to_refund"


def test_a_blank_reason_is_refused(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    for reason in ("", "   "):
        with pytest.raises(ValidationError) as exc:
            services.create_refund(payment, amount="1.00", reason=reason, user=admin_user)
        assert exc.value.error_dict["reason"][0].code == "reason_required"
    assert Refund.objects.filter(payment=payment).count() == 0


@pytest.mark.parametrize("bad", ["-1", "0", "abc"])
def test_bad_refund_amounts_are_refused(payment, admin_user, bad):
    services.mark_received(payment, user=admin_user)
    with pytest.raises(ValidationError):
        services.create_refund(payment, amount=bad, reason="x", user=admin_user)


def test_a_gateway_refund_transaction_id_is_recorded(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    refund = services.create_refund(payment, amount="10.00", reason="x", user=admin_user, transaction_id="GW-REFUND-1")
    assert refund.transaction_id == "GW-REFUND-1"


def test_refund_history_accumulates_and_is_ordered_newest_first(payment, admin_user):
    services.mark_received(payment, user=admin_user)
    services.create_refund(payment, amount="1.00", reason="a", user=admin_user)
    services.create_refund(payment, amount="1.00", reason="b", user=admin_user)
    assert [r.reason for r in payment.refunds.all()] == ["b", "a"]
