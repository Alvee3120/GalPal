"""
Review business logic: creating a review (storefront or an Admin's manual/testimonial entry),
moderation (approve/reject/reply), and the product rating aggregate.

`Product.average_rating`/`review_count` (declared in Module 4, unused until now) are recomputed by
`signals.py` on every save/delete of a `Review` — this app owns them, the same pattern Module 11
used for `Order.payment_status`.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.utils import timezone

from apps.catalog.exceptions import Conflict
from apps.catalog.models import Product
from apps.core.utils import discard_file
from apps.core.validators import validate_image_file
from apps.orders.models import OrderStatus

from .exceptions import field_error
from .models import Review, ReviewImage, ReviewStatus

RATING_PLACES = Decimal("0.01")
INACTIVE_ORDER_STATUSES = (OrderStatus.CANCELLED, OrderStatus.FAILED)  # an order that never really happened isn't a purchase


def is_verified_purchase(user, product):
    """True if `user` has ever had `product` on an order that wasn't cancelled/failed."""
    if user is None or not user.pk:
        return False
    return product.order_items.filter(order__customer=user).exclude(order__status__in=INACTIVE_ORDER_STATUSES).exists()


def recompute_product_rating(product_id):
    """Recompute `average_rating`/`review_count` from this product's APPROVED reviews only."""
    stats = Review.objects.filter(product_id=product_id, status=ReviewStatus.APPROVED).aggregate(avg=Avg("rating"), count=Count("id"))
    average = Decimal(str(stats["avg"])).quantize(RATING_PLACES, rounding=ROUND_HALF_UP) if stats["avg"] is not None else Decimal("0.00")
    Product.all_objects.filter(pk=product_id).update(average_rating=average, review_count=stats["count"])


def rating_breakdown(product):
    """`{5: n, 4: n, 3: n, 2: n, 1: n}` of APPROVED reviews, every star always present (0 if none)."""
    counts = dict(
        Review.objects.filter(product=product, status=ReviewStatus.APPROVED).values_list("rating").annotate(n=Count("id"))
    )
    return {star: counts.get(star, 0) for star in range(5, 0, -1)}


def _save_images(review, images):
    for index, image in enumerate(images or []):
        validate_image_file(image)
        ReviewImage.objects.create(review=review, image=image, sort_order=index)


@transaction.atomic
def create_review(*, product, user, rating, text, title="", images=None):
    """A customer's own review. One per product per customer — a repeat attempt is a 409."""
    if Review.objects.filter(product=product, user=user).exists():
        raise Conflict("You have already reviewed this product.", code="already_reviewed")
    try:
        with transaction.atomic():
            review = Review.objects.create(
                product=product, user=user, reviewer_name=user.full_name, rating=rating, title=title, text=text,
                is_verified_purchase=is_verified_purchase(user, product),
            )
    except IntegrityError:  # lost a race with a second, concurrent submission from the same customer
        raise Conflict("You have already reviewed this product.", code="already_reviewed") from None
    _save_images(review, images)
    return review


@transaction.atomic
def create_manual_review(*, product, rating, text, reviewer_name="", user=None, title="", status=ReviewStatus.APPROVED, created_by, images=None):
    """
    A review an Admin enters by hand (`is_manual`, `created_by`). Either for a real account (`user`): it then shows
    under that person's name, gets the Verified Purchase badge only if they really bought the product, and — like a
    customer's own review — is limited to one per product per account (409 `already_reviewed`); or a testimonial /
    import with just a `reviewer_name` and no account, which has no such limit. Purchase is never required to review
    (the badge is only a badge), so there's no purchase rule to apply here either.
    """
    if user is not None:
        if Review.objects.filter(product=product, user=user).exists():
            raise Conflict("This customer has already reviewed this product.", code="already_reviewed")
        reviewer_name = user.full_name
    try:
        with transaction.atomic():
            review = Review.objects.create(
                product=product, user=user, reviewer_name=reviewer_name, rating=rating, title=title, text=text,
                status=status, is_manual=True, created_by=created_by,
                is_verified_purchase=is_verified_purchase(user, product) if user is not None else False,
            )
    except IntegrityError:  # a concurrent review for the same account and product won the race
        raise Conflict("This customer has already reviewed this product.", code="already_reviewed") from None
    _save_images(review, images)
    return review


def set_status(review, status, *, user):
    if status not in ReviewStatus.values:
        raise field_error("status", "Not a valid status.", "invalid_status")
    review.status = status
    review.save(update_fields=["status", "updated_at"])
    return review


def approve(review, *, user):
    return set_status(review, ReviewStatus.APPROVED, user=user)


def reject(review, *, user):
    return set_status(review, ReviewStatus.REJECTED, user=user)


def reply(review, *, user, text):
    text = (text or "").strip()
    if not text:
        raise field_error("text", "A reply cannot be empty.", "reply_required")
    review.admin_reply = text
    review.admin_reply_at = timezone.now()
    review.replied_by = user if user and user.pk else None
    review.save(update_fields=["admin_reply", "admin_reply_at", "replied_by", "updated_at"])
    return review


def delete_review(review):
    product_id = review.product_id
    images = [image.image for image in review.images.all()]
    review.delete()
    for image in images:
        discard_file(image)
    return product_id
