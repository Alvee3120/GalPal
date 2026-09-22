from decimal import Decimal

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.catalog.tests.factories import ProductFactory, make_image
from apps.orders.tests.helpers import new_order
from apps.reviews.models import Review, ReviewStatus

pytestmark = pytest.mark.django_db

D = Decimal
REVIEWS = "/api/v1/reviews/"
BREAKDOWN = "/api/v1/reviews/breakdown/"


def details(response):
    return response.json()["error"]["details"]


def code(response):
    return response.json()["error"]["code"]


# --- listing --------------------------------------------------------------------------------------------------


def test_only_approved_reviews_are_public(api_client, product):
    Review.objects.create(product=product, reviewer_name="A", rating=5, text="Great", status=ReviewStatus.APPROVED)
    Review.objects.create(product=product, reviewer_name="B", rating=1, text="Pending", status=ReviewStatus.PENDING)
    Review.objects.create(product=product, reviewer_name="C", rating=1, text="Rejected", status=ReviewStatus.REJECTED)
    body = api_client.get(REVIEWS).json()
    assert body["count"] == 1 and body["results"][0]["reviewer_name"] == "A"


def test_the_public_shape_has_no_internal_fields(api_client, product):
    Review.objects.create(product=product, reviewer_name="A", rating=4, title="Nice", text="Good stuff", status=ReviewStatus.APPROVED, is_verified_purchase=True)
    row = api_client.get(REVIEWS).json()["results"][0]
    assert set(row) == {"id", "reviewer_name", "rating", "title", "text", "images", "is_verified_purchase", "admin_reply", "admin_reply_at", "created_at"}
    for hidden in ("status", "user", "is_manual", "created_by", "product"):
        assert hidden not in row
    assert row["is_verified_purchase"] is True


def test_filter_by_product_slug(api_client):
    a, b = ProductFactory(status="published"), ProductFactory(status="published")
    Review.objects.create(product=a, reviewer_name="A", rating=5, text="x", status=ReviewStatus.APPROVED)
    Review.objects.create(product=b, reviewer_name="B", rating=5, text="y", status=ReviewStatus.APPROVED)
    body = api_client.get(f"{REVIEWS}?product={a.slug}").json()
    assert body["count"] == 1 and body["results"][0]["reviewer_name"] == "A"


def test_filter_by_rating(api_client, product):
    Review.objects.create(product=product, reviewer_name="A", rating=5, text="x", status=ReviewStatus.APPROVED)
    Review.objects.create(product=product, reviewer_name="B", rating=2, text="y", status=ReviewStatus.APPROVED)
    assert api_client.get(f"{REVIEWS}?rating=5").json()["count"] == 1


def test_newest_first_by_default(api_client, product):
    Review.objects.create(product=product, reviewer_name="Old", rating=5, text="x", status=ReviewStatus.APPROVED)
    Review.objects.create(product=product, reviewer_name="New", rating=5, text="y", status=ReviewStatus.APPROVED)
    names = [r["reviewer_name"] for r in api_client.get(REVIEWS).json()["results"]]
    assert names == ["New", "Old"]


def test_a_review_with_images_shows_absolute_urls(api_client, product):
    from apps.reviews import services

    services.create_manual_review(product=product, reviewer_name="A", rating=5, text="x", created_by=None, images=[make_image()])
    row = api_client.get(REVIEWS).json()["results"][0]
    assert row["images"][0]["image"].startswith("http://testserver/media/reviews/")


def test_a_stale_token_does_not_break_the_public_list(api_client, product):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
    assert api_client.get(REVIEWS).status_code == 200


def test_pagination_shape(api_client, product):
    for i in range(3):
        Review.objects.create(product=product, reviewer_name=f"R{i}", rating=5, text="x", status=ReviewStatus.APPROVED)
    body = api_client.get(f"{REVIEWS}?page_size=2").json()
    assert set(body) == {"count", "next", "previous", "results"} and body["count"] == 3 and len(body["results"]) == 2


# --- breakdown -------------------------------------------------------------------------------------------------


def test_breakdown_reads_the_products_denormalized_fields(api_client, product):
    Review.objects.create(product=product, reviewer_name="A", rating=5, text="x", status=ReviewStatus.APPROVED)
    Review.objects.create(product=product, reviewer_name="B", rating=3, text="y", status=ReviewStatus.APPROVED)
    body = api_client.get(f"{BREAKDOWN}?product={product.slug}").json()
    assert body == {"average_rating": "4.00", "review_count": 2, "breakdown": {"5": 1, "4": 0, "3": 1, "2": 0, "1": 0}}


def test_breakdown_with_no_reviews(api_client, product):
    body = api_client.get(f"{BREAKDOWN}?product={product.slug}").json()
    assert body == {"average_rating": "0.00", "review_count": 0, "breakdown": {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}}


def test_breakdown_requires_a_known_product(api_client):
    assert api_client.get(f"{BREAKDOWN}?product=does-not-exist").status_code == 404


def test_breakdown_requires_the_product_param(api_client):
    assert api_client.get(BREAKDOWN).status_code == 404


# --- creating a review -------------------------------------------------------------------------------------------------


def test_anonymous_cannot_post_a_review(api_client, product):
    r = api_client.post(REVIEWS, {"product_id": product.id, "rating": 5, "text": "x"}, format="multipart")
    assert r.status_code == 401 and Review.objects.count() == 0


def test_a_customer_can_post_a_review(auth_client, customer, product):
    r = auth_client(customer).post(REVIEWS, {"product_id": product.id, "rating": 5, "title": "Love it", "text": "Works great"}, format="multipart")
    assert r.status_code == 201, r.json()
    body = r.json()
    assert (body["reviewer_name"], body["rating"], body["title"]) == (customer.full_name, 5, "Love it")
    review = Review.objects.get()
    assert review.status == "pending" and review.is_manual is False


def test_staff_cannot_post_a_review(auth_client, admin_user, cce_user, product):
    for staff in (admin_user, cce_user):
        r = auth_client(staff).post(REVIEWS, {"product_id": product.id, "rating": 5, "text": "x"}, format="multipart")
        assert r.status_code == 403
    assert Review.objects.count() == 0


def test_a_pending_review_does_not_show_up_publicly_yet(auth_client, customer, product):
    auth_client(customer).post(REVIEWS, {"product_id": product.id, "rating": 5, "text": "x"}, format="multipart")
    assert api_client_list(product) == 0


def api_client_list(product):
    from rest_framework.test import APIClient

    return APIClient().get(f"{REVIEWS}?product={product.slug}").json()["count"]


def test_a_repeat_review_is_a_409(auth_client, customer, product):
    client = auth_client(customer)
    client.post(REVIEWS, {"product_id": product.id, "rating": 5, "text": "x"}, format="multipart")
    r = client.post(REVIEWS, {"product_id": product.id, "rating": 1, "text": "y"}, format="multipart")
    assert r.status_code == 409 and code(r) == "already_reviewed"
    assert Review.objects.count() == 1


@pytest.mark.parametrize(("rating", "field"), [(0, "rating"), (6, "rating"), ("x", "rating")])
def test_bad_ratings_are_refused(auth_client, customer, product, rating, field):
    r = auth_client(customer).post(REVIEWS, {"product_id": product.id, "rating": rating, "text": "x"}, format="multipart")
    assert r.status_code == 400 and field in details(r)


def test_text_is_required(auth_client, customer, product):
    r = auth_client(customer).post(REVIEWS, {"product_id": product.id, "rating": 5}, format="multipart")
    assert r.status_code == 400 and "text" in details(r)


def test_an_unpublished_product_cannot_be_reviewed(auth_client, customer):
    draft = ProductFactory(status="draft")
    r = auth_client(customer).post(REVIEWS, {"product_id": draft.id, "rating": 5, "text": "x"}, format="multipart")
    assert r.status_code == 400 and "product_id" in details(r)


def test_a_review_is_flagged_verified_when_the_customer_bought_it(auth_client, customer, product):
    new_order(customer=customer, product=product)
    r = auth_client(customer).post(REVIEWS, {"product_id": product.id, "rating": 5, "text": "x"}, format="multipart")
    assert r.json()["is_verified_purchase"] is True


def test_a_review_can_include_images(auth_client, customer, product):
    r = auth_client(customer).post(REVIEWS, {"product_id": product.id, "rating": 5, "text": "x", "images": [make_image(), make_image("b.png")]}, format="multipart")
    assert r.status_code == 201 and len(r.json()["images"]) == 2


def test_too_many_images_are_refused(auth_client, customer, product):
    r = auth_client(customer).post(REVIEWS, {"product_id": product.id, "rating": 5, "text": "x", "images": [make_image() for _ in range(6)]}, format="multipart")
    assert r.status_code == 400 and "images" in details(r)
