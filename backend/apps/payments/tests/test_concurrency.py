"""
Two things happening to the same payment at once. Real threads and real transactions
(`transaction=True`), because the guarantees under test are ones the database's row lock provides,
which a single-connection test that rolls back can never exercise.
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection

from apps.orders.tests.helpers import new_order
from apps.payments import services
from apps.payments.models import Payment

from .conftest import callback_body, sign

D = Decimal


def run_together(jobs):
    barrier = threading.Barrier(len(jobs))

    def wrap(job):
        try:
            barrier.wait(timeout=10)
            return job()
        except Exception as exc:  # noqa: BLE001 - inspected by the test
            return exc
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        return list(pool.map(wrap, jobs))


@pytest.mark.django_db(transaction=True)
def test_concurrent_mark_received_calls_cannot_over_collect(admin_user):
    order = new_order(admin_user)  # amount = 570.00
    payment = Payment.objects.get(order=order)
    jobs = [lambda: services.mark_received(payment, amount="200.00", user=admin_user) for _ in range(4)]
    results = run_together(jobs)
    ok = [r for r in results if not isinstance(r, Exception)]
    rejected = [r for r in results if isinstance(r, Exception)]
    # 570.00 owed, four attempts of 200.00: only two can fit (400.00); the other two must be rejected,
    # never allowed to push amount_received past what is actually owed.
    assert len(ok) == 2 and all(isinstance(r, ValidationError) for r in rejected), results
    payment.refresh_from_db()
    assert payment.amount_received == D("400.00") and payment.amount_received <= payment.amount


@pytest.mark.django_db(transaction=True)
def test_concurrent_identical_webhook_deliveries_do_not_double_count(admin_user, settings):
    settings.PAYMENT_STUB_GATEWAY_SECRET = "dev-stub-secret-change-me"
    order = new_order(admin_user)
    payment = Payment.objects.get(order=order)
    payment, result = services.initiate_payment(payment, user=admin_user)
    body = callback_body(result.reference, "success", payment.amount)
    headers = {"X-Stub-Signature": sign(body)}
    results = run_together([lambda: services.handle_callback("stub", body, headers) for _ in range(6)])
    assert not [r for r in results if isinstance(r, Exception)], results
    payment.refresh_from_db()
    assert payment.amount_received == payment.amount and payment.status == "paid"  # not doubled, tripled, ...


@pytest.mark.django_db(transaction=True)
def test_concurrent_refunds_cannot_over_refund(admin_user):
    order = new_order(admin_user)
    payment = Payment.objects.get(order=order)
    services.mark_received(payment, user=admin_user)  # fully paid, 570.00
    jobs = [lambda i=i: services.create_refund(payment, amount="200.00", reason=f"r{i}", user=admin_user) for i in range(4)]
    results = run_together(jobs)
    ok = [r for r in results if not isinstance(r, Exception)]
    assert len(ok) == 2, results  # 200*3=600 > 570; only 2 of the 4 can succeed
    payment.refresh_from_db()
    assert services.net_received(payment) >= 0
