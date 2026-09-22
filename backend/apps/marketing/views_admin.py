"""Admin endpoint: read-only visibility into every tracking send, for debugging. Admin only."""
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets

from apps.accounts.permissions import IsAdmin

from .filters import AdminTrackingEventFilter
from .models import TrackingEventLog
from .serializers import TrackingEventLogSerializer

TAG = ["Admin – Marketing"]


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="List tracking event sends", description="Filters: `event_name`, `destination`, `success`, `is_manual_order`, `order`. `search` matches the event id or the order number."),
    retrieve=extend_schema(tags=TAG, summary="Tracking event detail", description="Includes the exact payload sent and the destination's response, for debugging a failed or rejected send."),
)
class AdminTrackingEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    queryset = TrackingEventLog.objects.select_related("order", "user")
    serializer_class = TrackingEventLogSerializer
    filterset_class = AdminTrackingEventFilter
    search_fields = ["event_id", "order__number"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
