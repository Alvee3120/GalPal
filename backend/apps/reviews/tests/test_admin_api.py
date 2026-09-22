import pytest

from apps.catalog.tests.factories import ProductFactory, make_image
from apps.reviews.models import Review, ReviewStatus

pytestmark = pytest.mark.django_db

REVIEWS = "/api/v1/admin/reviews/"


def url(review, suffix=""):
    return f"{REVIEWS}{review.id}/{suffix}"


def details(response):
    return response.json()["error"]["details"]


def make(product, **kw):
    kw.setdefault("reviewer_name", "A")
    kw.setdefault("rating", 5)
    kw.setdefault("text", "x")
    return Review.objects.create(product=product, **kw)


@pytest.fixture
def review(product):
    return make(product, status=ReviewStatus.PENDING)


# --- access control --------------------------------------------------------------------------------------------


def every_route(review):
    return [
        ("get", REVIEWS), ("post", REVIEWS), ("get", url(review)), ("patch", url(review)), ("delete", url(review)),
        ("post", url(review, "approve/")), ("post", url(review, "reject/")), ("post", url(review, "status/")),
        ("post", url(review, "reply/")),
    ]


def test_anonymous_gets_401_everywhere(api_client, review):
    for verb, path in every_route(review):
        assert getattr(api_client, verb)(path, {}, format="json").status_code == 401, (verb, path)


def test_customers_get_403_everywhere(auth_client, customer, review):
    client = auth_client(customer)
    for verb, path in every_route(review):
        assert getattr(client, verb)(path, {}, format="json").status_code == 403, (verb, path)


def test_cce_gets_403_everywhere(auth_client, cce_user, review):
    client = auth_client(cce_user)
    for verb, path in every_route(review):
        assert getattr(client, verb)(path, {}, format="json").status_code == 403, (verb, path)


def test_the_route_sweep_covers_reviews_too():
    from apps.accounts.tests import route_sweep

    assert any("/admin/reviews/" in route for route in route_sweep.admin_routes())


# --- list / detail --------------------------------------------------------------------------------------------------


def test_list_shows_every_status_and_full_detail(admin_client, product):
    make(product, status=ReviewStatus.PENDING)
    make(product, status=ReviewStatus.APPROVED)
    make(product, status=ReviewStatus.REJECTED)
    assert admin_client.get(REVIEWS).json()["count"] == 3


def test_detail_shape(admin_client, customer, product):
    review = make(product, user=customer, status=ReviewStatus.APPROVED, is_verified_purchase=True)
    body = admin_client.get(url(review)).json()
    assert set(body) == {
        "id", "product", "user", "reviewer_name", "rating", "title", "text", "images", "status", "is_verified_purchase",
        "admin_reply", "admin_reply_at", "replied_by", "is_manual", "created_by", "created_at", "updated_at",
    }
    assert body["user"] == {"id": customer.id, "full_name": customer.full_name} and body["status"] == "approved"


def test_filter_by_status_verified_manual_rating_and_product(admin_client, product):
    make(product, status=ReviewStatus.PENDING, is_verified_purchase=True)
    make(product, status=ReviewStatus.APPROVED, is_manual=True, rating=2)
    other = ProductFactory(status="published")
    make(other, status=ReviewStatus.APPROVED)
    assert admin_client.get(f"{REVIEWS}?status=pending").json()["count"] == 1
    assert admin_client.get(f"{REVIEWS}?is_verified_purchase=true").json()["count"] == 1
    assert admin_client.get(f"{REVIEWS}?is_manual=true").json()["count"] == 1
    assert admin_client.get(f"{REVIEWS}?rating=2").json()["count"] == 1
    assert admin_client.get(f"{REVIEWS}?product={product.slug}").json()["count"] == 2


def test_search_by_reviewer_text_and_product_name(admin_client, product):
    make(product, reviewer_name="Karim Uddin", text="excellent quality")
    body = admin_client.get(f"{REVIEWS}?search=karim").json()
    assert body["count"] == 1
    assert admin_client.get(f"{REVIEWS}?search=excellent").json()["count"] == 1
    assert admin_client.get(f"{REVIEWS}?search={product.name}").json()["count"] == 1


def test_404_and_put_not_supported(admin_client, review):
    assert admin_client.get(f"{REVIEWS}99999/").status_code == 404
    assert admin_client.put(url(review), {}, format="json").status_code == 405


# --- editing -------------------------------------------------------------------------------------------------------------


def test_admin_can_edit_content_and_status(admin_client, review):
    r = admin_client.patch(url(review), {"title": "Edited", "rating": 3, "status": "approved"}, format="json")
    assert r.status_code == 200
    body = r.json()
    assert (body["title"], body["rating"], body["status"]) == ("Edited", 3, "approved")


def test_editing_a_rating_recomputes_the_average(admin_client, product):
    review = make(product, status=ReviewStatus.APPROVED, rating=5)
    admin_client.patch(url(review), {"rating": 1}, format="json")
    product.refresh_from_db()
    assert product.average_rating == 1


def test_read_only_fields_cannot_be_set_by_the_client(admin_client, customer, review):
    r = admin_client.patch(url(review), {"user": customer.id, "is_manual": True, "is_verified_purchase": True, "admin_reply": "hacked"}, format="json")
    review.refresh_from_db()
    assert r.status_code == 200 and (review.user, review.is_manual, review.is_verified_purchase, review.admin_reply) == (None, False, False, "")


# --- deleting --------------------------------------------------------------------------------------------------------------


def test_deleting_a_review_removes_it_and_recomputes(admin_client, product):
    review = make(product, status=ReviewStatus.APPROVED, rating=5)
    assert admin_client.delete(url(review)).status_code == 204
    assert not Review.objects.filter(pk=review.pk).exists()
    product.refresh_from_db()
    assert product.review_count == 0


def test_deleting_removes_its_images(admin_client, product, django_capture_on_commit_callbacks):
    from django.core.files.storage import default_storage

    with django_capture_on_commit_callbacks(execute=True):
        r = admin_client.post(REVIEWS, {"product_id": product.id, "reviewer_name": "A", "rating": 5, "text": "x", "images": [make_image()]}, format="multipart")
    name = r.json()["images"][0]["image"].split("/media/")[1]
    assert default_storage.exists(name)
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.delete(f"{REVIEWS}{r.json()['id']}/")
    assert not default_storage.exists(name)


# --- manual/testimonial creation --------------------------------------------------------------------------------------------------


def test_create_a_manual_review(admin_client, admin_user, product):
    r = admin_client.post(REVIEWS, {"product_id": product.id, "reviewer_name": "Imported Customer", "rating": 5, "title": "Great", "text": "Testimonial text"}, format="multipart")
    assert r.status_code == 201, r.json()
    body = r.json()
    assert (body["reviewer_name"], body["status"], body["is_manual"]) == ("Imported Customer", "approved", True)
    assert body["created_by"] == {"id": admin_user.id, "full_name": admin_user.full_name} and body["user"] is None
    product.refresh_from_db()
    assert product.review_count == 1


def test_create_a_manual_review_with_an_explicit_status(admin_client, product):
    r = admin_client.post(REVIEWS, {"product_id": product.id, "reviewer_name": "A", "rating": 5, "text": "x", "status": "pending"}, format="multipart")
    assert r.json()["status"] == "pending"
    product.refresh_from_db()
    assert product.review_count == 0


def test_manual_reviews_can_repeat_for_the_same_product(admin_client, product):
    for _ in range(3):
        admin_client.post(REVIEWS, {"product_id": product.id, "reviewer_name": "A", "rating": 5, "text": "x"}, format="multipart")
    assert Review.objects.filter(product=product).count() == 3


def test_manual_review_required_fields(admin_client, product):
    r = admin_client.post(REVIEWS, {"product_id": product.id}, format="multipart")
    assert r.status_code == 400 and {"reviewer_name", "rating", "text"} <= set(details(r))


# --- moderation & reply --------------------------------------------------------------------------------------------------------------


def test_approve_and_reject(admin_client, review):
    r = admin_client.post(url(review, "approve/"), {}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "approved"
    r = admin_client.post(url(review, "reject/"), {}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "rejected"


def test_generic_status_endpoint(admin_client, review):
    r = admin_client.post(url(review, "status/"), {"status": "approved"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "approved"


def test_an_unknown_status_value_is_a_400(admin_client, review):
    assert admin_client.post(url(review, "status/"), {"status": "on-hold"}, format="json").status_code == 400


def test_approving_updates_the_product_rating(admin_client, product):
    review = make(product, status=ReviewStatus.PENDING, rating=4)
    admin_client.post(url(review, "approve/"), {}, format="json")
    product.refresh_from_db()
    assert (product.average_rating, product.review_count) == (4, 1)


def test_reply_records_who_and_when(admin_client, admin_user, review):
    r = admin_client.post(url(review, "reply/"), {"text": "Thanks for your feedback!"}, format="json")
    assert r.status_code == 200
    body = r.json()
    assert body["admin_reply"] == "Thanks for your feedback!" and body["replied_by"] == {"id": admin_user.id, "full_name": admin_user.full_name}
    assert body["admin_reply_at"] is not None


def test_an_empty_reply_is_refused(admin_client, review):
    r = admin_client.post(url(review, "reply/"), {"text": ""}, format="json")
    assert r.status_code == 400 and "text" in details(r)


def test_a_reply_shows_up_publicly_once_the_review_is_approved(api_client, admin_client, review):
    admin_client.post(url(review, "approve/"), {}, format="json")
    admin_client.post(url(review, "reply/"), {"text": "Thanks!"}, format="json")
    body = api_client.get(f"/api/v1/reviews/?product={review.product.slug}").json()["results"][0]
    assert body["admin_reply"] == "Thanks!"
