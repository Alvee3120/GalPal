from rest_framework import serializers

from apps.catalog.models import Product

from .models import Review, ReviewImage, ReviewStatus


class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = ["id", "image"]


# --- public ------------------------------------------------------------------------------------------


class PublicReviewSerializer(serializers.ModelSerializer):
    """An approved review, as shown on the storefront. No user id, status, or manual/staff bookkeeping."""

    images = ReviewImageSerializer(many=True, read_only=True)

    class Meta:
        model = Review
        fields = [
            "id", "reviewer_name", "rating", "title", "text", "images", "is_verified_purchase",
            "admin_reply", "admin_reply_at", "created_at",
        ]


class RatingBreakdownSerializer(serializers.Serializer):
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    review_count = serializers.IntegerField()
    breakdown = serializers.DictField(child=serializers.IntegerField(), help_text='Star (as a string, "5".."1") -> count of approved reviews.')


class CreateReviewSerializer(serializers.Serializer):
    """A customer's own review. `images` (optional) may be repeated multipart fields, up to 5."""

    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.filter(status="published"))
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=150, required=False, allow_blank=True)
    text = serializers.CharField(max_length=3000)
    images = serializers.ListField(
        child=serializers.ImageField(), required=False, allow_empty=True, max_length=5, help_text="Up to 5 images."
    )


# --- admin --------------------------------------------------------------------------------------------------


class _PersonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()


class AdminReviewSerializer(serializers.ModelSerializer):
    images = ReviewImageSerializer(many=True, read_only=True)
    user = serializers.SerializerMethodField()
    replied_by = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id", "product", "user", "reviewer_name", "rating", "title", "text", "images", "status",
            "is_verified_purchase", "admin_reply", "admin_reply_at", "replied_by", "is_manual", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "user", "is_verified_purchase", "admin_reply", "admin_reply_at", "replied_by", "is_manual", "created_by", "created_at", "updated_at"]

    def get_user(self, obj) -> dict | None:
        return None if obj.user_id is None else {"id": obj.user_id, "full_name": obj.user.full_name}

    def get_replied_by(self, obj) -> dict | None:
        return None if obj.replied_by_id is None else {"id": obj.replied_by_id, "full_name": obj.replied_by.full_name}

    def get_created_by(self, obj) -> dict | None:
        return None if obj.created_by_id is None else {"id": obj.created_by_id, "full_name": obj.created_by.full_name}


class ManualReviewSerializer(serializers.Serializer):
    """An Admin's testimonial/import: a product, a name, a star rating and text, with no customer account."""

    product_id = serializers.PrimaryKeyRelatedField(source="product", queryset=Product.objects.all())
    reviewer_name = serializers.CharField(max_length=150)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    title = serializers.CharField(max_length=150, required=False, allow_blank=True)
    text = serializers.CharField(max_length=3000)
    status = serializers.ChoiceField(choices=ReviewStatus.choices, default=ReviewStatus.APPROVED)
    images = serializers.ListField(child=serializers.ImageField(), required=False, allow_empty=True, max_length=5)


class ReviewStatusChangeSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ReviewStatus.choices)


class ReplySerializer(serializers.Serializer):
    text = serializers.CharField(max_length=2000)
