"""Admin endpoints: coupon CRUD and usage history. Admin only (CCE gets 403 — coupons are not
part of the order module CCE is scoped to)."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import viewsets

from apps.accounts.permissions import IsAdmin
from apps.catalog.exceptions import Conflict
from apps.core.serializers import ErrorResponseSerializer

from .models import Coupon, CouponUsage
from .serializers import AdminCouponSerializer, CouponUsageSerializer

ERR = OpenApiResponse(ErrorResponseSerializer)


@extend_schema_view(
    list=extend_schema(tags=["Admin – Coupons"], summary="List coupons (including inactive/expired)"),
    retrieve=extend_schema(tags=["Admin – Coupons"], summary="Get a coupon"),
    create=extend_schema(tags=["Admin – Coupons"], summary="Create a coupon", responses={201: AdminCouponSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Coupons"], summary="Update a coupon", responses={200: AdminCouponSerializer, 400: ERR}),
    destroy=extend_schema(
        tags=["Admin – Coupons"], summary="Delete a coupon",
        description="Blocked (409) if the coupon has ever been used — deactivate it instead.",
    ),
)
class AdminCouponViewSet(viewsets.ModelViewSet):
    serializer_class = AdminCouponSerializer
    permission_classes = [IsAdmin]
    queryset = Coupon.objects.prefetch_related("products", "categories", "brands")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["is_active", "type"]
    search_fields = ["code", "description"]
    ordering_fields = ["created_at", "code", "expiry_at"]
    ordering = ["-created_at"]

    def perform_destroy(self, instance):
        used = instance.usages.count()
        if used:
            # CouponUsage.coupon is PROTECT (the audit trail must survive); say so nicely, not as a 500.
            raise Conflict(
                f"This coupon has been used {used} time(s). Deactivate it instead of deleting it.",
                code="coupon_has_usages",
                details={"usage_count": used},
            )
        instance.delete()


@extend_schema_view(
    list=extend_schema(
        tags=["Admin – Coupons"], summary="Coupon usage history",
        description="Filter by `?coupon=<id>`. Every redemption Module 10's checkout has recorded.",
    ),
)
class AdminCouponUsageViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CouponUsageSerializer
    permission_classes = [IsAdmin]
    queryset = CouponUsage.objects.select_related("coupon", "user")
    filterset_fields = ["coupon"]
    ordering = ["-created_at"]
