"""Audit log endpoint (Module 18), mounted at /api/v1/admin/audit-logs/. Admin only (IsAdmin), read-only."""

import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters, serializers, viewsets

from apps.accounts.permissions import IsAdmin

from .models import AuditLog

TAG = ["Admin – Audit Log"]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id", "created_at", "actor", "actor_name", "actor_role", "action", "target_type", "target_id", "target_label",
            "changes", "metadata", "ip_address", "user_agent", "method", "path", "status_code",
        ]
        read_only_fields = fields


class AuditLogFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    kind = django_filters.ChoiceFilter(choices=[("event", "Events"), ("request", "Requests")], method="filter_kind")
    action = django_filters.CharFilter(field_name="action", lookup_expr="startswith")

    class Meta:
        model = AuditLog
        fields = ["actor", "actor_role", "action", "target_type", "target_id"]

    def filter_kind(self, queryset, name, value):
        return queryset.filter(action__startswith="api.") if value == "request" else queryset.exclude(action__startswith="api.")


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="Audit log", description="Admin/CCE write actions, newest first. Filter `kind` "
                       "(event|request), `action` (prefix, e.g. `order.`), `actor`, `actor_role`, `target_type`/`target_id`, "
                       "`date_from`/`date_to`; `search` actor, target, path or IP."),
    retrieve=extend_schema(tags=TAG, summary="One audit entry"),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = AuditLogFilter
    search_fields = ["actor_name", "target_label", "target_id", "path", "ip_address"]
