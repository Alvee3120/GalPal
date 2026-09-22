from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.tests.factories import UserFactory
from apps.catalog.exceptions import Conflict
from apps.catalog.tests.factories import ProductFactory, ProductVariantFactory
from apps.orders import services as order_services
from apps.orders.models import Order
from apps.orders.tests.helpers import new_order
from apps.reviews import services
from apps.reviews.models import Review, ReviewImage, ReviewStatus

pytestmark = pytest.mark.django_db

D = Decimal


# --- verified purchase ------------------------------------------------------------------------------------


def test_a_customer_who_bought_the_product_is_verified(customer, product):
    new_order(customer=customer, product=product)
    assert services.is_verified_purchase(customer, product) is True


def test_a_customer_who_never_ordered_is_not_verified(customer, product):
    assert services.is_verified_purchase(customer, product) is False


def test_ordering_a_different_product_does_not_verify_this_one(customer, product):
    new_order(customer=customer)  # its own product, not `product`
    assert services.is_verified_purchase(customer, product) is False


@pytest.mark.parametrize("status", ["cancelled", "failed"])
def test_a_cancelled_or_failed_order_does_not_verify(customer, product, admin_user, status):
    order = new_order(customer=customer, product=product)
    Order.objects.filter(pk=order.pk).update(status=status)
    assert services.is_verified_purchase(customer, product) is False


def test_a_returned_or_delivered_order_still_verifies(customer, product):
    order = new_order(customer=customer, product=product)
    Order.objects.filter(pk=order.pk).update(status="delivered")
    assert services.is_verified_purchase(customer, product) is True


def test_a_manual_staff_order_for_the_customer_still_verifies(customer, product, admin_user):
    order_services.create_manual_order(staff=admin_user, data={
        "name": customer.full_name, "phone": customer.phone, "district": "Dhaka", "address_line": "H1",
        "source": "call", "payment_method": "cod", "items": [{"product_id": product.id, "quantity": 1}], "customer": customer,
    })
    assert services.is_verified_purchase(customer, product) is True


def test_a_guest_order_with_the_same_phone_does_not_verify_a_customer_account(customer, product):
    new_order(product=product, phone=customer.phone)  # guest order, no `customer` link
    assert services.is_verified_purchase(customer, product) is False


def test_no_user_is_never_verified(product):
    assert services.is_verified_purchase(None, product) is False


# --- rating aggregate --------------------------------------------------------------------------------------------


def test_a_new_pending_review_does_not_move_the_average(product):
    Review.objects.create(product=product, reviewer_name="A", rating=1, text="x", status=ReviewStatus.PENDING)
    product.refresh_from_db()
    assert (product.average_rating, product.review_count) == (D("0.00"), 0)


def test_approving_folds_it_into_the_average(product):
    review = Review.objects.create(product=product, reviewer_name="A", rating=4, text="x", status=ReviewStatus.PENDING)
    services.approve(review, user=None)
    product.refresh_from_db()
    assert (product.average_rating, product.review_count) == (D("4.00"), 1)


def test_the_average_is_of_approved_reviews_only(product):
    for rating, status in [(5, ReviewStatus.APPROVED), (3, ReviewStatus.APPROVED), (1, ReviewStatus.PENDING), (1, ReviewStatus.REJECTED)]:
        Review.objects.create(product=product, reviewer_name="A", rating=rating, text="x", status=status)
    product.refresh_from_db()
    assert (product.average_rating, product.review_count) == (D("4.00"), 2)


def test_the_average_rounds_to_two_places(product):
    for rating in (5, 5, 4):  # 14/3 = 4.666...
        Review.objects.create(product=product, reviewer_name="A", rating=rating, text="x", status=ReviewStatus.APPROVED)
    product.refresh_from_db()
    assert product.average_rating == D("4.67")


def test_rejecting_an_approved_review_removes_it_from_the_average(product):
    review = Review.objects.create(product=product, reviewer_name="A", rating=5, text="x", status=ReviewStatus.APPROVED)
    services.reject(review, user=None)
    product.refresh_from_db()
    assert (product.average_rating, product.review_count) == (D("0.00"), 0)


def test_editing_an_approved_reviews_rating_updates_the_average(product):
    review = Review.objects.create(product=product, reviewer_name="A", rating=5, text="x", status=ReviewStatus.APPROVED)
    review.rating = 1
    review.save()
    product.refresh_from_db()
    assert product.average_rating == D("1.00")


def test_deleting_an_approved_review_updates_the_average(product):
    a = Review.objects.create(product=product, reviewer_name="A", rating=5, text="x", status=ReviewStatus.APPROVED)
    b = Review.objects.create(product=product, reviewer_name="B", rating=1, text="x", status=ReviewStatus.APPROVED)
    services.delete_review(a)
    product.refresh_from_db()
    assert (product.average_rating, product.review_count) == (D("1.00"), 1)
    assert Review.objects.filter(pk=b.pk).exists()


def test_a_raw_orm_edit_from_the_shell_still_recomputes(product):
    """The signal fires on any save, not just ones that go through services."""
    review = Review.objects.create(product=product, reviewer_name="A", rating=2, text="x", status=ReviewStatus.PENDING)
    review.status = ReviewStatus.APPROVED
    review.save()
    product.refresh_from_db()
    assert product.review_count == 1


def test_reviews_on_a_different_product_do_not_affect_this_one(product):
    other = ProductFactory(status="published", stock_quantity=20, manage_stock=True)
    Review.objects.create(product=other, reviewer_name="A", rating=1, text="x", status=ReviewStatus.APPROVED)
    product.refresh_from_db()
    assert product.review_count == 0


def test_rating_breakdown_counts_every_star_and_only_approved(product):
    Review.objects.create(product=product, reviewer_name="A", rating=5, text="x", status=ReviewStatus.APPROVED)
    Review.objects.create(product=product, reviewer_name="B", rating=5, text="x", status=ReviewStatus.APPROVED)
    Review.objects.create(product=product, reviewer_name="C", rating=3, text="x", status=ReviewStatus.APPROVED)
    Review.objects.create(product=product, reviewer_name="D", rating=1, text="x", status=ReviewStatus.PENDING)
    assert services.rating_breakdown(product) == {5: 2, 4: 0, 3: 1, 2: 0, 1: 0}


def test_rating_breakdown_with_no_reviews_is_all_zero(product):
    assert services.rating_breakdown(product) == {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}


# --- create_review (customer) -----------------------------------------------------------------------------------------


def test_create_review_snapshots_the_reviewers_name_and_verified_flag(customer, product):
    new_order(customer=customer, product=product)
    review = services.create_review(product=product, user=customer, rating=5, text="Great!")
    assert (review.reviewer_name, review.status, review.is_verified_purchase, review.is_manual) == (customer.full_name, "pending", True, False)


def test_create_review_without_a_purchase_is_not_verified(customer, product):
    review = services.create_review(product=product, user=customer, rating=3, text="ok")
    assert review.is_verified_purchase is False


def test_a_second_review_by_the_same_customer_is_a_409(customer, product):
    services.create_review(product=product, user=customer, rating=5, text="Great!")
    with pytest.raises(Conflict) as exc:
        services.create_review(product=product, user=customer, rating=1, text="Actually no")
    assert exc.value.get_codes() == "already_reviewed"
    assert Review.objects.filter(product=product, user=customer).count() == 1


def test_two_different_customers_can_each_review_the_same_product(product):
    a, b = UserFactory(), UserFactory()
    services.create_review(product=product, user=a, rating=5, text="x")
    services.create_review(product=product, user=b, rating=1, text="y")
    assert Review.objects.filter(product=product).count() == 2


def test_the_same_customer_can_review_two_different_products(customer):
    a, b = ProductFactory(status="published", stock_quantity=20, manage_stock=True), ProductFactory(status="published", stock_quantity=20, manage_stock=True)
    services.create_review(product=a, user=customer, rating=5, text="x")
    services.create_review(product=b, user=customer, rating=1, text="y")
    assert Review.objects.filter(user=customer).count() == 2


def test_the_database_also_enforces_one_review_per_customer_per_product(customer, product):
    Review.objects.create(product=product, user=customer, reviewer_name=customer.full_name, rating=5, text="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        Review.objects.create(product=product, user=customer, reviewer_name=customer.full_name, rating=1, text="y")


def test_manual_reviews_with_no_user_have_no_such_limit(product):
    services.create_manual_review(product=product, reviewer_name="A", rating=5, text="x", created_by=None)
    services.create_manual_review(product=product, reviewer_name="B", rating=4, text="y", created_by=None)
    assert Review.objects.filter(product=product, user__isnull=True).count() == 2


# --- create_manual_review (admin) ------------------------------------------------------------------------------------------


def test_manual_review_defaults_to_approved_and_is_flagged(admin_user, product):
    review = services.create_manual_review(product=product, reviewer_name="Imported Customer", rating=5, text="Testimonial", created_by=admin_user)
    assert (review.status, review.is_manual, review.user, review.is_verified_purchase) == ("approved", True, None, False)
    assert review.created_by == admin_user
    product.refresh_from_db()
    assert product.review_count == 1


def test_manual_review_can_be_created_pending(admin_user, product):
    review = services.create_manual_review(product=product, reviewer_name="A", rating=5, text="x", status=ReviewStatus.PENDING, created_by=admin_user)
    assert review.status == "pending"
    product.refresh_from_db()
    assert product.review_count == 0


# --- moderation & reply -------------------------------------------------------------------------------------------------------


def test_set_status_rejects_an_unknown_value(product):
    """Short enough to fit the column (10 chars), so this can only fail via the choices check itself."""
    review = Review.objects.create(product=product, reviewer_name="A", rating=5, text="x")
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError) as exc:
        services.set_status(review, "on-hold", user=None)
    assert exc.value.error_dict["status"][0].code == "invalid_status"
    review.refresh_from_db()
    assert review.status == "pending"


def test_reply_stamps_who_and_when(admin_user, product):
    review = Review.objects.create(product=product, reviewer_name="A", rating=5, text="x", status=ReviewStatus.APPROVED)
    services.reply(review, user=admin_user, text="Thank you!")
    review.refresh_from_db()
    assert review.admin_reply == "Thank you!" and review.replied_by == admin_user and review.admin_reply_at is not None


def test_an_empty_reply_is_refused(admin_user, product):
    review = Review.objects.create(product=product, reviewer_name="A", rating=5, text="x")
    from django.core.exceptions import ValidationError

    for text in ("", "   "):
        with pytest.raises(ValidationError) as exc:
            services.reply(review, user=admin_user, text=text)
        assert exc.value.error_dict["text"][0].code == "reply_required"


# --- images ------------------------------------------------------------------------------------------------------------------------


def test_deleting_a_review_removes_its_images_from_storage(product, django_capture_on_commit_callbacks):
    from apps.catalog.tests.factories import make_image
    from django.core.files.storage import default_storage

    with django_capture_on_commit_callbacks(execute=True):
        review = services.create_manual_review(product=product, reviewer_name="A", rating=5, text="x", created_by=None, images=[make_image()])
    name = review.images.get().image.name
    assert default_storage.exists(name)
    with django_capture_on_commit_callbacks(execute=True):
        services.delete_review(review)
    assert not default_storage.exists(name) and not ReviewImage.objects.filter(review_id=review.pk).exists()
