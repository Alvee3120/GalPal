import django_filters
from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.core.validators import normalize_bd_phone

from .models import User


class _UserSearchMixin(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method="filter_search", help_text="Name, phone (any Bangladesh format) or email."
    )
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        query = Q(full_name__icontains=value) | Q(email__icontains=value) | Q(phone__icontains=value)
        try:
            # "+880 1712-345678" should find 01712345678
            query |= Q(phone=normalize_bd_phone(value))
        except ValidationError:
            pass
        return queryset.filter(query)


class CustomerFilter(_UserSearchMixin):
    class Meta:
        model = User
        fields = ["is_active", "created_via_checkout"]


class StaffFilter(_UserSearchMixin):
    class Meta:
        model = User
        fields = ["is_active", "role"]
