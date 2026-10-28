import django_filters

from . import services
from .models import Brand, Category, ProductStatus, Tag


class _TopLevelMixin(django_filters.FilterSet):
    top_level = django_filters.BooleanFilter(method="filter_top_level", help_text="true = only top-level categories")

    def filter_top_level(self, queryset, name, value):
        return queryset.filter(parent__isnull=bool(value))


class PublicCategoryFilter(_TopLevelMixin):
    parent = django_filters.CharFilter(field_name="parent__slug", help_text="Slug of the parent category")

    class Meta:
        model = Category
        fields = []


class PublicBrandFilter(django_filters.FilterSet):
    """Brands that sell products in a category — the category itself and all of its sub-categories (the same
    coverage as the product list's `category` filter), published products only."""

    category = django_filters.CharFilter(method="filter_category", help_text="Category slug (includes its sub-categories)")

    class Meta:
        model = Brand
        fields = []

    def filter_category(self, queryset, name, value):
        category = Category.objects.filter(slug=value).values("id").first()
        if category is None:
            return queryset.none()
        ids = services.descendant_ids(category["id"], services.parent_map())
        ids.add(category["id"])
        return queryset.filter(
            products__status=ProductStatus.PUBLISHED, products__category_links__category_id__in=ids
        ).distinct()


class AdminCategoryFilter(_TopLevelMixin):
    parent = django_filters.NumberFilter(field_name="parent_id", help_text="Id of the parent category")

    class Meta:
        model = Category
        fields = ["is_active"]


class AdminBrandFilter(django_filters.FilterSet):
    class Meta:
        model = Brand
        fields = ["is_active"]


class AdminTagFilter(django_filters.FilterSet):
    class Meta:
        model = Tag
        fields = []
