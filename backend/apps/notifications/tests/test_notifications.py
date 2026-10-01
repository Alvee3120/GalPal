"""Module 16 — templates, the notification log (secrets masked), retries, and the shop's triggers."""

from unittest import mock

import pytest
from django.core import mail

from apps.accounts.tests.factories import UserFactory
from apps.core.messaging import LocMemSMSBackend
from apps.notifications import services
from apps.notifications.models import Channel, Event, LogStatus, NotificationLog, NotificationTemplate

pytestmark = pytest.mark.django_db

A = "/api/v1/admin/notifications/"


@pytest.fixture
def run_on_commit(django_capture_on_commit_callbacks):
    def run(fn):
        with django_capture_on_commit_callbacks(execute=True):
            return fn()
    return run


# --- access ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["logs/", "templates/"])
def test_notification_admin_is_admin_only(api_client, auth_client, cce_user, customer, path):
    assert api_client.get(A + path).status_code == 401
    assert auth_client(cce_user).get(A + path).status_code == 403
    assert auth_client(customer).get(A + path).status_code == 403


# --- sending + log ------------------------------------------------------------------------------------------------------


def test_notify_sends_both_channels_and_logs(run_on_commit):
    logs = run_on_commit(lambda: services.notify(Event.BACK_IN_STOCK, phone="01712345678", email="a@example.com", context={"product_name": "Rose Serum"}))
    assert len(logs) == 1  # back-in-stock has no email template: only the SMS goes
    assert LocMemSMSBackend.outbox[0]["to"] == "01712345678" and "Rose Serum" in LocMemSMSBackend.outbox[0]["message"]
    log = NotificationLog.objects.get()
    assert log.status == LogStatus.SENT and log.attempts == 1 and log.sent_at


def test_no_recipient_means_no_message():
    assert services.notify(Event.ORDER_PLACED, context={}) == []
    assert NotificationLog.objects.count() == 0


def test_secrets_are_sent_but_masked_in_the_log():
    user = UserFactory(email="r@example.com", phone="01712345678")
    services.password_reset_code(user, "482913", by_email=True)
    assert "482913" in mail.outbox[0].body
    log = NotificationLog.objects.get()
    assert "482913" not in log.body and services.MASK in log.body and log.has_secret and log.status == LogStatus.SENT


def test_failed_send_retries_then_fails(run_on_commit, settings):
    settings.NOTIFICATION_MAX_ATTEMPTS = 3
    with mock.patch("apps.notifications.services.send_sms", side_effect=RuntimeError("provider down")):
        run_on_commit(lambda: services.notify(Event.BACK_IN_STOCK, phone="01712345678", context={"product_name": "X"}))
    log = NotificationLog.objects.get()
    assert log.status == LogStatus.FAILED and log.attempts == 3 and "provider down" in log.error


def test_admin_can_resend_a_failed_log(auth_client, admin_user, run_on_commit):
    log = NotificationLog.objects.create(event=Event.BACK_IN_STOCK, channel=Channel.SMS, recipient="01712345678", body="hi", status=LogStatus.FAILED, attempts=3)
    r = run_on_commit(lambda: auth_client(admin_user).post(f"{A}logs/{log.pk}/retry/"))
    assert r.status_code == 200
    log.refresh_from_db()
    assert log.status == LogStatus.SENT


def test_a_log_with_a_secret_cannot_be_resent(auth_client, admin_user):
    log = NotificationLog.objects.create(event=Event.PASSWORD_RESET, channel=Channel.SMS, recipient="01712345678", body="••••••", has_secret=True, status=LogStatus.FAILED)
    assert auth_client(admin_user).post(f"{A}logs/{log.pk}/retry/").status_code == 400


# --- templates -----------------------------------------------------------------------------------------------------------


def test_admin_template_overrides_and_reset(auth_client, admin_user, run_on_commit):
    client = auth_client(admin_user)
    url = f"{A}templates/back_in_stock/sms/"
    assert client.put(url, {"body": "{product_name} is back! {bogus}"}, format="json").status_code == 400
    assert client.put(url, {"body": "{product_name} is back!"}, format="json").status_code == 200
    run_on_commit(lambda: services.notify(Event.BACK_IN_STOCK, phone="01712345678", context={"product_name": "Rose"}))
    assert LocMemSMSBackend.outbox[-1]["message"] == "Rose is back!"
    assert client.delete(url).json()["is_custom"] is False
    assert not NotificationTemplate.objects.exists()


def test_secret_placeholder_must_stay(auth_client, admin_user):
    r = auth_client(admin_user).put(f"{A}templates/password_reset_otp/sms/", {"body": "Your code is coming"}, format="json")
    assert r.status_code == 400


def test_switched_off_template_sends_nothing():
    NotificationTemplate.objects.create(event=Event.BACK_IN_STOCK, channel=Channel.SMS, body="x", is_active=False)
    assert services.notify(Event.BACK_IN_STOCK, phone="01712345678", context={}) == []


def test_render_never_evaluates_attributes():
    assert services.render("{name.__class__} {name}", {"name": "Rina"}) == "{name.__class__} Rina"
