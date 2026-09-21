import django_filters

from .models import Order


class OrderFilter(django_filters.FilterSet):
    """Filters for the staff order list. `date_from` / `date_to` are inclusive calendar dates."""

    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    created_by = django_filters.NumberFilter(field_name="created_by_id")

    class Meta:
        model = Order
        fields = ["status", "source", "payment_status", "is_manual", "customer", "district"]
