"""Storefront "Notify Me": ask to be texted when an out-of-stock product (or variant) is back."""
from django.db.models import Prefetch
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_field, extend_schema_view
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCatalogStaff
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .models import ProductVariant, StockNotification
from .throttles import StockNotificationThrottle


class StockNotificationRequestSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=20, help_text="Guests only; ignored when logged in.")


class StockNotificationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(allow_null=True)


class StockNotificationView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [StockNotificationThrottle]

    @extend_schema(
        tags=["Catalog"], summary="Notify me when back in stock",
        description=(
            "Logged in: texts the account's phone. Guest: send `phone`. 400 if the item is in stock or not available, "
            "409 `already_subscribed` if this phone is already waiting for it. The SMS goes out when stock is added."
        ),
        request=StockNotificationRequestSerializer,
        responses={201: StockNotificationSerializer, 400: OpenApiResponse(ErrorResponseSerializer), 409: OpenApiResponse(ErrorResponseSerializer)},
    )
    def post(self, request):
        serializer = StockNotificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        created = services.subscribe_to_restock(
            product_id=data["product_id"], variant_id=data.get("variant_id"), phone=data.get("phone"), user=request.user,
        )
        return Response(StockNotificationSerializer(created).data, status=status.HTTP_201_CREATED)


# --- staff: who is waiting for what (Admin + CCE) ---------------------------------------------------------------------


class _NotificationProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    sku = serializers.CharField()
    slug = serializers.CharField()
    feature_image = serializers.ImageField()


class _NotificationVariantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sku = serializers.CharField()
    label = serializers.SerializerMethodField()

    def get_label(self, obj) -> str:
        return ", ".join(v.value for v in obj.attribute_values.all())


class StaffStockNotificationSerializer(serializers.ModelSerializer):
    product = _NotificationProductSerializer(read_only=True)
    variant = _NotificationVariantSerializer(read_only=True, allow_null=True)
    customer_name = serializers.CharField(source="user.full_name", read_only=True, allow_null=True, default=None)
    status = serializers.SerializerMethodField()
    in_stock_now = serializers.SerializerMethodField()

    class Meta:
        model = StockNotification
        fields = ["id", "product", "variant", "phone", "customer_name", "status", "in_stock_now", "created_at", "notified_at"]
        read_only_fields = fields

    def get_status(self, obj) -> str:
        return "notified" if obj.notified_at else "waiting"

    @extend_schema_field(serializers.BooleanField())
    def get_in_stock_now(self, obj):
        return services._is_available(obj.product, obj.variant)


class StockNotificationStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["waiting", "notified"])


class StockNotificationStatusFilter(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        value = request.query_params.get("status")
        if value == "waiting":
            return queryset.filter(notified_at__isnull=True)
        if value == "notified":
            return queryset.filter(notified_at__isnull=False)
        return queryset


@extend_schema_view(
    list=extend_schema(
        tags=["Admin – Products"], summary="Notify Me requests",
        description="Who asked to be texted when an item is back in stock. `?status=waiting|notified`, `?search=` phone, product name or SKU.",
        parameters=[OpenApiParameter("status", str, enum=["waiting", "notified"])],
    ),
    partial_update=extend_schema(
        tags=["Admin – Products"], summary="Mark a Notify Me request waiting / notified",
        description=(
            "For staff who contacted the customer themselves (`notified`), or to put a request back in the queue "
            "(`waiting`) so the automatic SMS goes out on the next restock."
        ),
        request=StockNotificationStatusUpdateSerializer, responses={200: StaffStockNotificationSerializer},
    ),
)
class StaffStockNotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsCatalogStaff]
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = StaffStockNotificationSerializer
    filter_backends = [StockNotificationStatusFilter, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["phone", "product__name", "product__sku", "variant__sku", "user__full_name"]
    ordering_fields = ["created_at", "notified_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        variants = ProductVariant.objects.prefetch_related("attribute_values")
        return StockNotification.objects.select_related("product", "user").prefetch_related(
            Prefetch("variant", queryset=variants), Prefetch("product__variants", queryset=variants)
        )

    def partial_update(self, request, pk=None):
        notification = self.get_object()
        serializer = StockNotificationStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["status"] == "notified":
            notification.notified_at = notification.notified_at or timezone.now()
        else:
            notification.notified_at = None
        notification.save(update_fields=["notified_at", "updated_at"])
        return Response(self.get_serializer(self.get_queryset().get(pk=notification.pk)).data)
