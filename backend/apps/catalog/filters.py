import django_filters

from .models import Brand, Category, Tag


class _TopLevelMixin(django_filters.FilterSet):
    top_level = django_filters.BooleanFilter(method="filter_top_level", help_text="true = only top-level categories")

    def filter_top_level(self, queryset, name, value):
        return queryset.filter(parent__isnull=bool(value))


class PublicCategoryFilter(_TopLevelMixin):
    parent = django_filters.CharFilter(field_name="parent__slug", help_text="Slug of the parent category")

    class Meta:
        model = Category
        fields = []


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
