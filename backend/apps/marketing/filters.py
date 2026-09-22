import django_filters

from .models import TrackingEventLog


class AdminTrackingEventFilter(django_filters.FilterSet):
    class Meta:
        model = TrackingEventLog
        fields = ["event_name", "destination", "success", "is_manual_order", "order"]
