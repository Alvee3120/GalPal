import django_filters
from django.db.models import F, Q
from django.utils import timezone

from .models import Coupon


class AdminCouponFilter(django_filters.FilterSet):
    """`status` follows `services.status_of` (it needs the view's `usage_count_db` annotation for "used_up")."""

    status = django_filters.ChoiceFilter(
        method="filter_status",
        choices=[(s, s) for s in ("active", "inactive", "scheduled", "expired", "used_up")],
    )

    class Meta:
        model = Coupon
        fields = ["is_active", "type"]

    def filter_status(self, queryset, name, value):
        now = timezone.now()
        started = Q(start_at__isnull=True) | Q(start_at__lte=now)
        not_expired = Q(expiry_at__isnull=True) | Q(expiry_at__gte=now)
        used_up = Q(total_usage_limit__isnull=False, usage_count_db__gte=F("total_usage_limit"))
        if value == "inactive":
            return queryset.filter(is_active=False)
        if value == "scheduled":
            return queryset.filter(is_active=True, start_at__gt=now)
        if value == "expired":
            return queryset.filter(is_active=True, expiry_at__lt=now).filter(started)
        live = queryset.filter(is_active=True).filter(started & not_expired)
        return live.filter(used_up) if value == "used_up" else live.exclude(used_up)
