"""Discount management (Admin only), mounted at /api/v1/admin/discounts/. CCE and customers get 403."""

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, viewsets

from apps.accounts.permissions import IsAdmin

from . import services
from .models import Discount, DiscountKind, DiscountStatus, DiscountTarget
from .serializers import AdminDiscountSerializer

TAG = ["Admin – Discounts"]


@extend_schema_view(
    list=extend_schema(
        tags=TAG, summary="Discounts",
        description="`search` name; `status` (active / scheduled / expired / inactive — from is_active, the window and now), "
                    "`kind` (percentage / fixed), `target_type` (category / products).",
        parameters=[
            OpenApiParameter("status", str, enum=DiscountStatus.values),
            OpenApiParameter("kind", str, enum=DiscountKind.values),
            OpenApiParameter("target_type", str, enum=DiscountTarget.values),
        ],
    ),
    retrieve=extend_schema(tags=TAG, summary="One discount"),
    create=extend_schema(tags=TAG, summary="Create a discount", description="Category target: `category_id` (its "
                         "sub-categories are included). Products target: `product_ids`. Dates are ISO datetimes."),
    partial_update=extend_schema(tags=TAG, summary="Edit / activate / deactivate a discount"),
    destroy=extend_schema(tags=TAG, summary="Delete a discount", description="Orders already placed keep their prices; "
                          "to keep the record, switch it off (`is_active: false`) instead."),
)
class DiscountViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminDiscountSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        queryset = Discount.objects.select_related("category", "created_by").prefetch_related("products")
        params = self.request.query_params
        if params.get("status") in DiscountStatus.values:
            queryset = queryset.filter(services.status_q(params["status"]))
        if params.get("kind") in DiscountKind.values:
            queryset = queryset.filter(kind=params["kind"])
        if params.get("target_type") in DiscountTarget.values:
            queryset = queryset.filter(target_type=params["target_type"])
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
        services.invalidate()

    def perform_update(self, serializer):
        serializer.save()
        services.invalidate()

    def perform_destroy(self, instance):
        instance.delete()
        services.invalidate()

