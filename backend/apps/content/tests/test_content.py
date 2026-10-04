"""Module 15 — CMS pages, FAQs, newsletter, announcement bar and global search."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.content import services
from apps.content.models import Announcement, Faq, NewsletterSubscriber, Page

pytestmark = pytest.mark.django_db

A = "/api/v1/admin/content/"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


# --- access ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["pages/", "faqs/", "newsletter/", "announcements/", "newsletter/export/"])
def test_content_admin_is_admin_only(api_client, auth_client, cce_user, customer, path):
    assert api_client.get(A + path).status_code == 401
    assert auth_client(cce_user).get(A + path).status_code == 403
    assert auth_client(customer).get(A + path).status_code == 403


# --- pages ----------------------------------------------------------------------------------------------------------------


def test_page_crud_and_public_read(admin_client, api_client):
    res = admin_client.post(A + "pages/", {"title": "Shipping Policy", "slug": "shipping-policy", "content": "## Delivery\n- 2 days"}, format="json")
    assert res.status_code == 201, res.content
    assert res.json()["is_standard"] is True
    assert api_client.get("/api/v1/pages/shipping-policy/").json()["content"].startswith("## Delivery")

    pk = res.json()["id"]
    assert admin_client.patch(f"{A}pages/{pk}/", {"slug": "shipping"}, format="json").status_code == 400  # standard slug locked
    admin_client.patch(f"{A}pages/{pk}/", {"is_active": False}, format="json")
    assert api_client.get("/api/v1/pages/shipping-policy/").status_code == 404


# --- FAQs -----------------------------------------------------------------------------------------------------------------


def test_public_faqs_hide_inactive(admin_client, api_client):
    admin_client.post(A + "faqs/", {"category": "Orders", "question": "How do I order?", "answer": "Add to cart."}, format="json")
    Faq.objects.create(question="Hidden?", answer="Yes", is_active=False)
    questions = [f["question"] for f in api_client.get("/api/v1/faqs/").json()]
    assert questions == ["How do I order?"]


# --- newsletter -----------------------------------------------------------------------------------------------------------


def test_subscribe_dedupes_and_reactivates(api_client):
    url = "/api/v1/newsletter/subscribe/"
    assert api_client.post(url, {"email": "A@Example.com"}, format="json").status_code == 201
    assert api_client.post(url, {"email": "a@example.com", "phone": "+8801712345678"}, format="json").status_code == 201
    sub = NewsletterSubscriber.objects.get()
    assert (sub.email, sub.phone) == ("a@example.com", "01712345678")

    assert api_client.post("/api/v1/newsletter/unsubscribe/", {"token": sub.token}, format="json").status_code == 200
    sub.refresh_from_db()
    assert not sub.is_subscribed
    api_client.post(url, {"phone": "01712345678"}, format="json")
    sub.refresh_from_db()
    assert sub.is_subscribed


def test_subscribe_needs_contact_and_valid_phone(api_client):
    url = "/api/v1/newsletter/subscribe/"
    assert api_client.post(url, {}, format="json").status_code == 400
    assert api_client.post(url, {"phone": "12345"}, format="json").status_code == 400


def test_unsubscribe_unknown_token(api_client):
    assert api_client.post("/api/v1/newsletter/unsubscribe/", {"token": "nope"}, format="json").status_code == 404


def test_admin_subscriber_list_toggle_and_export(admin_client):
    sub = services.subscribe(email="x@example.com")
    services.subscribe(email="gone@example.com")
    services.unsubscribe(NewsletterSubscriber.objects.get(email="gone@example.com").token)
    assert admin_client.get(A + "newsletter/?is_subscribed=true").json()["count"] == 1
    csv_body = admin_client.get(A + "newsletter/export/").content.decode("utf-8")
    assert "x@example.com" in csv_body and "gone@example.com" not in csv_body
    admin_client.patch(f"{A}newsletter/{sub.pk}/", {"is_subscribed": False}, format="json")
    sub.refresh_from_db()
    assert not sub.is_subscribed and sub.unsubscribed_at
    assert "token" not in admin_client.get(A + "newsletter/").json()["results"][0]


# --- announcements --------------------------------------------------------------------------------------------------------


def test_announcement_window_and_link_validation(admin_client, api_client):
    now = timezone.now()
    Announcement.objects.create(text="Live")
    Announcement.objects.create(text="Later", starts_at=now + timedelta(days=1))
    Announcement.objects.create(text="Over", ends_at=now - timedelta(minutes=1))
    Announcement.objects.create(text="Off", is_active=False)
    assert [a["text"] for a in api_client.get("/api/v1/announcements/").json()] == ["Live"]

    bad = admin_client.post(A + "announcements/", {"text": "x", "link_url": "javascript:alert(1)"}, format="json")
    assert bad.status_code == 400
    assert admin_client.post(A + "announcements/", {"text": "x", "link_url": "//evil.example"}, format="json").status_code == 400
    assert admin_client.post(A + "announcements/", {"text": "Sale", "link_url": "/shop"}, format="json").status_code == 201


# --- search ---------------------------------------------------------------------------------------------------------------


def test_search_short_query_is_empty(api_client):
    body = api_client.get("/api/v1/search/?q=a").json()
    assert body["products"] == [] and body["suggestions"] == []


def test_page_model_str():
    assert str(Page(title="About Us")) == "About Us"


# --- homepage category sections ----------------------------------------------------------------------------------------


def test_homepage_sections_admin_crud_and_public_visibility(admin_client, api_client, auth_client, cce_user):
    from apps.catalog.models import Category
    from apps.catalog.services import invalidate_category_cache
    from apps.content.models import HomepageCategorySection

    makeup = Category.objects.create(name="Makeup", slug="makeup-x")
    hair = Category.objects.create(name="Hair", slug="hair-x")
    r = admin_client.post(A + "category-sections/", {"category_id": makeup.pk, "position": "before_video"}, format="json")
    assert r.status_code == 201 and r.json()["product_limit"] == 8 and r.json()["rows"] == 1  # the defaults
    admin_client.post(A + "category-sections/", {"category_id": hair.pk, "position": "after_video", "is_active": False}, format="json")
    assert admin_client.post(A + "category-sections/", {"category_id": hair.pk, "rows": 9}, format="json").status_code == 400
    assert auth_client(cce_user).get(A + "category-sections/").status_code == 403

    public = api_client.get("/api/v1/homepage/category-sections/").json()
    assert [(s["category"]["name"], s["position"]) for s in public] == [("Makeup", "before_video")]  # inactive one hidden

    Category.objects.filter(pk=makeup.pk).update(name="Make-up", is_active=True)
    invalidate_category_cache()
    assert api_client.get("/api/v1/homepage/category-sections/").json()[0]["category"]["name"] == "Make-up"  # title follows the category
    Category.objects.filter(pk=makeup.pk).update(is_active=False)
    invalidate_category_cache()
    assert api_client.get("/api/v1/homepage/category-sections/").json() == []  # a hidden category never breaks the page
    assert HomepageCategorySection.objects.count() == 2
