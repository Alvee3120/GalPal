"""Module 14 — customer care tools: profile/notes/tags, support inbox, abandoned checkouts."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.care import services
from apps.care.models import CheckoutLead, ContactMessage
from apps.orders.models import Order
from apps.orders.tests.helpers import new_order

pytestmark = pytest.mark.django_db

A = "/api/v1/admin/care/"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


def owned(order, customer):
    Order.objects.filter(pk=order.pk).update(customer=customer)
    order.refresh_from_db()
    return order


# --- access ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["customers/1/", "tags/", "messages/", "abandoned-checkouts/"])
def test_care_admin_is_admin_only(api_client, auth_client, cce_user, customer, path):
    assert api_client.get(A + path).status_code == 401
    assert auth_client(cce_user).get(A + path).status_code == 403
    assert auth_client(customer).get(A + path).status_code == 403


# --- customer profile ---------------------------------------------------------------------------------------------------


def test_profile_shows_orders_total_spent_notes_and_tags(admin_client, admin_user, customer):
    kept = owned(new_order(admin_user), customer)
    cancelled = owned(new_order(admin_user), customer)
    Order.objects.filter(pk=cancelled.pk).update(status="cancelled")
    admin_client.post(f"{A}customers/{customer.pk}/notes/", {"text": "Prefers evening calls"}, format="json")
    admin_client.put(f"{A}customers/{customer.pk}/tags/", {"tags": ["VIP", " vip ", "Risky"]}, format="json")
    profile = admin_client.get(f"{A}customers/{customer.pk}/").json()
    assert profile["stats"]["order_count"] == 2
    assert Decimal(profile["stats"]["total_spent"]) == kept.grand_total  # the cancelled order doesn't count
    assert [n["text"] for n in profile["notes"]] == ["Prefers evening calls"]
    assert sorted(t["name"] for t in profile["tags"]) == ["Risky", "VIP"]  # "vip" reused, not duplicated


def test_staff_accounts_have_no_care_profile(admin_client, cce_user):
    assert admin_client.get(f"{A}customers/{cce_user.pk}/").status_code == 404


# --- support inbox ------------------------------------------------------------------------------------------------------


def test_contact_form_needs_a_way_to_reply_and_lands_in_the_inbox(api_client, admin_client):
    body = {"name": "Rina", "message": "Is this serum safe for oily skin?"}
    assert api_client.post("/api/v1/contact/", body, format="json").status_code == 400
    assert api_client.post("/api/v1/contact/", {**body, "phone": "01712345678"}, format="json").status_code == 201
    inbox = admin_client.get(f"{A}messages/").json()["results"]
    assert inbox[0]["name"] == "Rina" and inbox[0]["status"] == "new"


def test_a_note_moves_a_new_message_in_progress_and_status_can_be_set(admin_client):
    message = ContactMessage.objects.create(name="Rina", phone="01712345678", message="Hi")
    r = admin_client.post(f"{A}messages/{message.pk}/notes/", {"text": "Called her back"}, format="json")
    assert r.status_code == 201 and r.json()["status"] == "in_progress" and r.json()["notes"][0]["text"] == "Called her back"
    r = admin_client.patch(f"{A}messages/{message.pk}/", {"status": "resolved"}, format="json")
    assert r.json()["status"] == "resolved"


# --- abandoned checkouts ------------------------------------------------------------------------------------------------


def test_checkout_capture_is_one_open_lead_per_phone(api_client):
    api_client.post("/api/v1/checkout/lead/", {"name": "Rina", "phone": "01712345678"}, format="json")
    api_client.post("/api/v1/checkout/lead/", {"name": "Rina Akter", "phone": "+8801712345678"}, format="json")
    lead = CheckoutLead.objects.get()
    assert lead.name == "Rina Akter" and lead.phone == "01712345678"


def test_an_invalid_phone_is_silently_ignored(api_client):
    assert api_client.post("/api/v1/checkout/lead/", {"phone": "123"}, format="json").status_code == 204
    assert not CheckoutLead.objects.exists()


def test_abandoned_only_after_the_wait_and_never_once_ordered(admin_client, admin_user):
    services.capture_checkout_lead(phone="01712345678", name="Rina")
    assert admin_client.get(f"{A}abandoned-checkouts/").json()["count"] == 0  # still typing
    CheckoutLead.objects.update(updated_at=timezone.now() - timedelta(minutes=45))
    assert admin_client.get(f"{A}abandoned-checkouts/").json()["count"] == 1
    new_order(admin_user)  # same phone places an order
    assert CheckoutLead.objects.get().status == "converted"
    assert admin_client.get(f"{A}abandoned-checkouts/").json()["count"] == 0


def test_a_lead_can_be_dismissed(admin_client):
    lead = services.capture_checkout_lead(phone="01712345678")
    CheckoutLead.objects.update(updated_at=timezone.now() - timedelta(hours=1))
    assert admin_client.patch(f"{A}abandoned-checkouts/{lead.pk}/", {"status": "dismissed"}, format="json").status_code == 200
    assert admin_client.get(f"{A}abandoned-checkouts/").json()["count"] == 0
    assert admin_client.get(f"{A}abandoned-checkouts/?status=dismissed").json()["count"] == 1
