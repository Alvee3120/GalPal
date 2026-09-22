import django_filters

from .models import Review


class PublicReviewFilter(django_filters.FilterSet):
    product = django_filters.CharFilter(field_name="product__slug", help_text="Product slug")
    rating = django_filters.NumberFilter(field_name="rating")

    class Meta:
        model = Review
        fields = []


class AdminReviewFilter(django_filters.FilterSet):
    product = django_filters.CharFilter(field_name="product__slug", help_text="Product slug")

    class Meta:
        model = Review
        fields = ["status", "is_verified_purchase", "is_manual", "rating"]
