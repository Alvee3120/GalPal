from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.catalog.models import Product
from apps.core.models import TimeStampedModel
from apps.core.utils import UploadPath
from apps.core.validators import validate_image_file


class ReviewStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class Review(TimeStampedModel):
    """
    A product review. `user` is the reviewing customer for a real, storefront-submitted review, and
    is null for an Admin-entered testimonial/import (`is_manual=True`) — the two cases are otherwise
    the same row shape (`reviewer_name` is always set, so which one a review is doesn't change how it
    displays). `is_verified_purchase` is computed once at creation from the customer's own order
    history (see `services.is_verified_purchase`) — it is only ever a badge, never a gate on who may
    review a product.

    Only APPROVED reviews count toward a product's `average_rating`/`review_count` (see `services`
    and `signals.py`, which recompute both on every save/delete of a review).
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviews")
    reviewer_name = models.CharField(max_length=150)

    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=150, blank=True)
    text = models.TextField(max_length=3000)

    status = models.CharField(max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.PENDING, db_index=True)
    is_verified_purchase = models.BooleanField(default=False)

    admin_reply = models.TextField(max_length=2000, blank=True)
    admin_reply_at = models.DateTimeField(null=True, blank=True)
    replied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    is_manual = models.BooleanField(default=False, help_text="Created by an Admin (a testimonial/import), not submitted by a customer.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="The staff member who entered this review, for a manual review.",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["product", "status"])]
        constraints = [
            # A real customer may review a product once; manual/testimonial reviews (user is null) have no such limit.
            models.UniqueConstraint(fields=["product", "user"], condition=Q(user__isnull=False), name="one_review_per_user_per_product"),
        ]

    def __str__(self):
        return f"{self.reviewer_name} on product {self.product_id}: {self.rating}*"


class ReviewImage(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=UploadPath("reviews"), validators=[validate_image_file])
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Image {self.pk} of review {self.review_id}"
