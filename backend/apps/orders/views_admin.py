"""
Admin/CCE order endpoints: the ONLY admin area a CCE can reach. Everything is Admin + CCE except the
two actions that stay Admin-only: deleting an order and overriding its shipping charge.
"""
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAdmin, IsAdminOrCCE
from apps.core.serializers import ErrorResponseSerializer
from apps.shipping import services as shipping_services
from apps.shipping.serializers import ShippingQuoteSerializer
from apps.site_settings.services import get_site_settings

from . import services
from .filters import OrderFilter
from .models import Order
from .serializers import (
    CustomerLookupSerializer,
    InvoiceSerializer,
    ManualOrderResultSerializer,
    ManualOrderSerializer,
    OrderNoteSerializer,
    OrderUpdateSerializer,
    PickerRowSerializer,
    ShippingHelperQuerySerializer,
    ShippingOverrideSerializer,
    StaffOrderListSerializer,
    StaffOrderSerializer,
    StatusChangeSerializer,
    build_invoice,
)

ERR = OpenApiResponse(ErrorResponseSerializer)
TAG = ["Admin – Orders"]
COURIER_FIELDS = ("courier_name", "tracking_id", "consignment_id")


@extend_schema_view(
    list=extend_schema(
        tags=TAG, summary="List orders",
        description=(
            "Filters: `status`, `source`, `payment_status`, `is_manual`, `created_by` (staff user id), `customer`, `district`, "
            "`date_from` / `date_to` (inclusive, YYYY-MM-DD). `search` matches order number, phone, name or email. "
            "`ordering`: `created_at`, `grand_total`, `number` (prefix `-` to reverse)."
        ),
    ),
    retrieve=extend_schema(tags=TAG, summary="Order detail (staff view)", responses={200: StaffOrderSerializer, 404: ERR}),
    destroy=extend_schema(
        tags=TAG, summary="Delete an order (Admin only)",
        description="Soft delete, and only for cancelled/failed/returned orders (409 `order_not_deletable` otherwise). CCE gets 403.",
        responses={204: None, 403: ERR, 409: ERR},
    ),
)
class AdminOrderViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsAdminOrCCE]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_class = OrderFilter
    search_fields = ["number", "phone", "customer_name", "email"]
    ordering_fields = ["created_at", "grand_total", "number"]
    ordering = ["-created_at", "-id"]

    def get_permissions(self):
        if self.action in ("destroy", "shipping_override"):
            return [IsAdmin()]  # a CCE may work orders, but never delete them or touch a shipping charge
        return super().get_permissions()

    def get_queryset(self):
        queryset = Order.objects.select_related("customer", "created_by")
        if self.action == "list":
            return queryset.prefetch_related("items")
        return queryset.prefetch_related("items", "history__changed_by", "notes__author")

    def get_serializer_class(self):
        return StaffOrderListSerializer if self.action == "list" else StaffOrderSerializer

    def perform_destroy(self, instance):
        services.delete_order(instance)

    def _detail(self, order):
        fresh = self.get_queryset().get(pk=order.pk)
        return Response(StaffOrderSerializer(fresh, context={"request": self.request}).data)

    @extend_schema(
        tags=TAG, summary="Create a manual order (phone / social)",
        description=(
            "Staff-entered order. `source` is required and chosen by the staff member; `created_by` and `is_manual` are set "
            "automatically. The delivery charge is resolved from the address (a CCE cannot type one). Guests are allowed "
            "(no account is ever created); pass `customer_id` from the phone lookup to link an existing customer. A similar "
            "recent order only produces a warning."
        ),
        request=ManualOrderSerializer, responses={201: ManualOrderResultSerializer, 400: ERR},
    )
    def create(self, request):
        serializer = ManualOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        placed = services.create_manual_order(staff=request.user, data=serializer.validated_data)
        order = self.get_queryset().get(pk=placed.order.pk)
        body = {"order": StaffOrderSerializer(order, context={"request": request}).data, "warnings": placed.warnings}
        return Response(body, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=TAG, summary="Edit a pending order",
        description=(
            "Only while `pending` (409 `order_not_editable` otherwise). Send only what changes; `items` replaces the item list. "
            "Everything is recalculated atomically: the delivery charge is re-resolved from the (new) address at the current "
            "zone charge, which also clears any Admin override; stock for the old lines is put back and the new lines taken."
        ),
        request=OrderUpdateSerializer, responses={200: StaffOrderSerializer, 400: ERR, 409: ERR},
    )
    def partial_update(self, request, pk=None):
        order = self.get_object()
        serializer = OrderUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_order(order, user=request.user, data=serializer.service_data())
        return self._detail(order)

    @extend_schema(
        tags=TAG, summary="Change the order status",
        description=(
            "pending → confirmed → processing → shipped → delivered, plus cancelled / returned / failed where allowed "
            "(see `allowed_transitions` on the order). Cancel, fail and return put the stock back. Courier fields may be sent "
            "with the change (typically when shipping)."
        ),
        request=StatusChangeSerializer, responses={200: StaffOrderSerializer, 400: ERR},
    )
    @action(detail=True, methods=["post"], url_path="status")
    def change_status(self, request, pk=None):
        order = self.get_object()
        serializer = StatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        services.change_status(
            order, data["status"], user=request.user, note=data.get("note", ""),
            courier={name: data.get(name, "") for name in COURIER_FIELDS},
        )
        return self._detail(order)

    @extend_schema(tags=TAG, summary="Internal notes on an order", responses=OrderNoteSerializer(many=True))
    @extend_schema(methods=["POST"], tags=TAG, summary="Add an internal note", request=OrderNoteSerializer, responses={201: OrderNoteSerializer})
    @action(detail=True, methods=["get", "post"], url_path="notes", pagination_class=None)
    def notes(self, request, pk=None):
        order = self.get_object()
        if request.method == "GET":
            return Response(OrderNoteSerializer(order.notes.select_related("author"), many=True).data)
        serializer = OrderNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = services.add_note(order, request.user, serializer.validated_data["text"])
        return Response(OrderNoteSerializer(note).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=TAG, summary="Override the shipping charge (Admin only)",
        description="A reason is required and is written to the order history. Allowed until the order ships. CCE gets 403.",
        request=ShippingOverrideSerializer, responses={200: StaffOrderSerializer, 400: ERR, 403: ERR, 409: ERR},
    )
    @action(detail=True, methods=["post"], url_path="shipping-override")
    def shipping_override(self, request, pk=None):
        order = self.get_object()
        serializer = ShippingOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.override_shipping(order, user=request.user, **serializer.validated_data)
        return self._detail(order)

    @extend_schema(tags=TAG, summary="Print-friendly invoice data", responses=InvoiceSerializer)
    @action(detail=True, methods=["get"], url_path="invoice", pagination_class=None)
    def invoice(self, request, pk=None):
        order = self.get_object()
        return Response(InvoiceSerializer(build_invoice(order, get_site_settings())).data)


# --- helpers for taking a phone order: read-only, minimal data -----------------------------------------------------


class _HelperView(APIView):
    permission_classes = [IsAdminOrCCE]


class HelperProductsView(_HelperView):
    @extend_schema(
        tags=TAG, summary="Order form: product / variant picker",
        description="Search by name or SKU. Each row is a buyable item (a variant row per active variant): id, name, sku, variant label, price, stock, image only. At most 20 products.",
        parameters=[OpenApiParameter("search", str, description="Name or SKU")], responses=PickerRowSerializer(many=True),
    )
    def get(self, request):
        rows = services.pickable_lines(request.query_params.get("search", ""))
        return Response(PickerRowSerializer(rows, many=True, context={"request": request}).data)


class HelperShippingView(_HelperView):
    @extend_schema(
        tags=TAG, summary="Order form: delivery charge for an address",
        description="Read-only preview using the zones the Admin configured. Same result the order will get.",
        parameters=[
            OpenApiParameter("district", str, required=True), OpenApiParameter("area", str),
            OpenApiParameter("subtotal", float, required=True), OpenApiParameter("delivery_method", str),
        ],
        responses={200: ShippingQuoteSerializer, 400: OpenApiResponse(ErrorResponseSerializer)},
    )
    def get(self, request):
        serializer = ShippingHelperQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        quote = shipping_services.calculate_shipping(
            {"district": data["district"], "area": data["area"]}, data["subtotal"], None,
            delivery_method=data["delivery_method"] or None,
        )
        return Response(ShippingQuoteSerializer(quote).data)


class HelperCustomerLookupView(_HelperView):
    @extend_schema(
        tags=TAG, summary="Order form: find a customer by phone",
        description="Returns only the name and saved addresses, to prefill the form. 404 if no customer has this phone.",
        parameters=[OpenApiParameter("phone", str, required=True)],
        responses={200: CustomerLookupSerializer, 400: ERR, 404: ERR},
    )
    def get(self, request):
        from .serializers import _phone  # same normaliser the forms use

        phone = request.query_params.get("phone")
        if not phone:
            raise ValidationError({"phone": ["This field is required."]})
        customer = User.objects.filter(
            Q(phone=_phone(phone)), role=User.Role.CUSTOMER, is_active=True
        ).prefetch_related("addresses").first()
        if customer is None:
            raise NotFound("No customer with this phone number.")
        return Response(CustomerLookupSerializer(customer).data)
