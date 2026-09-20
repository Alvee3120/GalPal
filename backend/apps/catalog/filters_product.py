"""Filters for the public product list and the admin product list."""

import django_filters
from django.db.models import Case, DecimalField, F, Q, Value, When
from django.utils import timezone

from . import services
from .models import Product, SkinType


def annotate_effective_price(queryset):
    """Add `effective_price_db`: the discount price while on sale, else the regular price."""
    now = timezone.now()
    on_sale = (
        Q(discount_price__isnull=False)
        & (Q(sale_start_at__isnull=True) | Q(sale_start_at__lte=now))
        & (Q(sale_end_at__isnull=True) | Q(sale_end_at__gte=now))
    )
    return queryset.annotate(
        effective_price_db=Case(
            When(on_sale, then=F("discount_price")),
            default=F("regular_price"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        on_sale_db=Case(When(on_sale, then=Value(True)), default=Value(False)),
        # Best-effort "popularity" until Orders (sales count) land: bestsellers first, then reviews.
        popularity_db=Case(When(is_bestseller=True, then=Value(1_000_000)), default=Value(0)) + F("review_count"),
    )


def _category_and_descendants(slug):
    from .models import Category

    category = Category.objects.filter(slug=slug).values("id").first()
    if category is None:
        return None
    ids = services.descendant_ids(category["id"], services.parent_map())
    ids.add(category["id"])
    return ids


class PublicProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(method="filter_category", help_text="Category slug (includes its sub-categories)")
    brand = django_filters.CharFilter(field_name="brand__slug")
    tag = django_filters.CharFilter(field_name="tags__slug")
    skin_type = django_filters.ChoiceFilter(choices=SkinType.choices, method="filter_skin_type")
    price_min = django_filters.NumberFilter(field_name="effective_price_db", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="effective_price_db", lookup_expr="lte")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")
    on_sale = django_filters.BooleanFilter(field_name="on_sale_db")
    gender = django_filters.CharFilter(field_name="gender")
    is_featured = django_filters.BooleanFilter(field_name="is_featured")
    is_new_arrival = django_filters.BooleanFilter(field_name="is_new_arrival")
    is_bestseller = django_filters.BooleanFilter(field_name="is_bestseller")

    class Meta:
        model = Product
        fields = []

    def filter_category(self, queryset, name, value):
        ids = _category_and_descendants(value)
        return queryset.none() if ids is None else queryset.filter(category_links__category_id__in=ids).distinct()

    def filter_skin_type(self, queryset, name, value):
        return queryset.filter(skin_type__contains=[value])

    def filter_in_stock(self, queryset, name, value):
        out_of_stock = Q(manage_stock=True) & Q(stock_status="out_of_stock")
        return queryset.exclude(out_of_stock) if value else queryset.filter(out_of_stock)


class AdminProductFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name="category_links__category_id")
    brand = django_filters.NumberFilter(field_name="brand_id")
    tag = django_filters.NumberFilter(field_name="tags__id")

    class Meta:
        model = Product
        fields = ["status", "is_featured", "is_new_arrival", "is_bestseller", "has_variants"]
