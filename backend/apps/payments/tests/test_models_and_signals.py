from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.catalog.tests.factories import ProductFactory
from apps.orders import services as order_services
from apps.orders.models import Order, PaymentMethod, PaymentStatus
from apps.orders.tests.helpers import new_order
from apps.payments.models import Payment, Refund, RefundStatus

pytestmark = pytest.mark.django_db

D = Decimal


# --- auto-creation --------------------------------------------------------------------------------------


def test_placing_an_order_creates_exactly_one_payment(admin_user):
    order = new_order(admin_user)
    payment = Payment.objects.get(order=order)
    assert (payment.method, payment.status, payment.amount, payment.amount_received) == (order.payment_method, "unpaid", order.grand_total, D("0.00"))
    assert payment.gateway == "" and payment.transaction_id == ""


def test_a_storefront_checkout_also_gets_a_payment(api_client, product):
    from apps.orders.tests.helpers import place

    place(api_client, product)
    order = Order.objects.get()
    assert Payment.objects.filter(order=order).count() == 1


def test_a_second_payment_for_the_same_order_is_rejected_at_the_database_level(order):
    with pytest.raises(IntegrityError), transaction.atomic():
        Payment.objects.create(order=order, method=PaymentMethod.COD, amount=D("10.00"))


# --- amount syncs with a pending edit, freezes once money moves --------------------------------------------------


def test_editing_a_pending_orders_items_updates_the_payments_amount(admin_user):
    product = ProductFactory(stock_quantity=10, manage_stock=True, regular_price="500.00")
    order = new_order(admin_user, product=product, quantity=1)
    order_services.update_order(order, user=admin_user, data={"items": [{"product_id": product.id, "quantity": 3}]})
    payment = Payment.objects.get(order=order)
    order.refresh_from_db()
    assert payment.amount == order.grand_total and payment.amount == D("1570.00")  # 3*500 + 70 shipping


def test_the_amount_is_frozen_once_something_has_been_collected(admin_user):
    from apps.payments import services as payment_services

    order = new_order(admin_user, quantity=1)  # subtotal 500 + 70 shipping = 570
    payment = Payment.objects.get(order=order)
    payment_services.mark_received(payment, amount="200.00", user=admin_user)
    order_services.update_order(order, user=admin_user, data={"note": "x"})  # a harmless edit, no item change
    payment.refresh_from_db()
    assert payment.amount == D("570.00")  # unchanged even though this path re-saves the order


def test_the_amount_is_frozen_after_a_failed_gateway_attempt_amount_still_zero(admin_user, settings):
    """Amount stays synced while FAILED and amount_received==0 (nothing has actually moved yet)."""
    from apps.payments import services as payment_services

    product = ProductFactory(stock_quantity=10, manage_stock=True, regular_price="500.00")
    order = new_order(admin_user, product=product, quantity=1)
    payment = Payment.objects.get(order=order)
    payment_services.initiate_payment(payment, user=admin_user)
    payment.refresh_from_db()
    from apps.payments.gateways import GatewayResult

    payment_services._apply_gateway_result(payment, GatewayResult(reference=payment.transaction_id, outcome="failed", amount=None))
    payment.refresh_from_db()
    assert payment.status == "failed"
    order_services.update_order(order, user=admin_user, data={"items": [{"product_id": product.id, "quantity": 2}]})
    payment.refresh_from_db()
    order.refresh_from_db()
    assert payment.amount == order.grand_total  # still syncing: FAILED + nothing collected


# --- database constraints -------------------------------------------------------------------------------


def make_payment(order, **kw):
    Payment.objects.filter(order=order).delete()
    return Payment(order=order, method=PaymentMethod.COD, amount=D("100.00"), **kw)


def test_amount_received_cannot_exceed_amount(order):
    with pytest.raises(IntegrityError), transaction.atomic():
        make_payment(order, amount_received=D("150.00")).save()


def test_amount_cannot_be_negative(order):
    with pytest.raises(IntegrityError), transaction.atomic():
        Payment(order=order, method=PaymentMethod.COD, amount=D("-1.00")).save()


def test_refund_amount_must_be_positive(payment):
    with pytest.raises(IntegrityError), transaction.atomic():
        Refund.objects.create(payment=payment, amount=D("0.00"), reason="x")


def test_deleting_a_payment_with_refunds_is_protected(payment):
    Refund.objects.create(payment=payment, amount=D("1.00"), reason="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        payment.delete()


def test_refund_status_default_is_completed(payment):
    refund = Refund.objects.create(payment=payment, amount=D("1.00"), reason="x")
    assert refund.status == RefundStatus.COMPLETED


def test_the_amount_is_frozen_even_when_partially_collected_and_the_order_is_edited(admin_user):
    """A partial COD collection on a still-pending order must not have its 'amount owed' rewritten by an edit."""
    from apps.payments import services as payment_services

    product = ProductFactory(stock_quantity=10, manage_stock=True, regular_price="500.00")
    order = new_order(admin_user, product=product, quantity=1)  # 500 + 70 shipping = 570
    payment = Payment.objects.get(order=order)
    payment_services.mark_received(payment, amount="100.00", user=admin_user)
    order_services.update_order(order, user=admin_user, data={"items": [{"product_id": product.id, "quantity": 3}]})
    payment.refresh_from_db()
    assert payment.amount == D("570.00")  # NOT re-synced to the new (larger) grand_total
