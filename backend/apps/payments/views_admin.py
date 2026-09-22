"""Admin endpoints: payment records, marking money received, gateway initiate/verify and refunds.
Admin only — CCE has no access here."""
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .models import Payment
from .serializers import (
    InitiatePaymentSerializer,
    InitiateResultSerializer,
    MarkReceivedSerializer,
    PaymentListSerializer,
    PaymentSerializer,
    RefundInputSerializer,
)

ERR = OpenApiResponse(ErrorResponseSerializer)
TAG = ["Admin – Payments"]


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="List payments", description="Filters: `status`, `method`, `gateway`, `order`. `search` matches the order number or the transaction id."),
    retrieve=extend_schema(tags=TAG, summary="Payment detail (with its refund history)"),
)
class AdminPaymentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    queryset = Payment.objects.select_related("order", "collected_by").prefetch_related("refunds__processed_by")
    filterset_fields = ["status", "method", "gateway", "order"]
    search_fields = ["order__number", "transaction_id"]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        return PaymentListSerializer if self.action == "list" else PaymentSerializer

    def _detail(self, payment, status_code=status.HTTP_200_OK):
        fresh = self.get_queryset().get(pk=payment.pk)
        return Response(PaymentSerializer(fresh, context=self.get_serializer_context()).data, status=status_code)

    @extend_schema(
        tags=TAG, summary="Mark money as received (e.g. Cash on Delivery collected)",
        description="`amount` defaults to whatever is still owed. Safe to call more than once for partial collections.",
        request=MarkReceivedSerializer, responses={200: PaymentSerializer, 400: ERR, 409: ERR},
    )
    @action(detail=True, methods=["post"], url_path="mark-received")
    def mark_received(self, request, pk=None):
        payment = self.get_object()
        serializer = MarkReceivedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        services.mark_received(payment, amount=data.get("amount"), note=data.get("note", ""), user=request.user)
        return self._detail(payment)

    @extend_schema(
        tags=TAG, summary="Start a gateway payment",
        description="Returns a redirect URL for the customer. Not restricted to online orders — useful for sending a Cash-on-Delivery customer a payment link too.",
        request=InitiatePaymentSerializer, responses={200: InitiateResultSerializer, 400: ERR, 409: ERR},
    )
    @action(detail=True, methods=["post"], url_path="initiate")
    def initiate(self, request, pk=None):
        payment = self.get_object()
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, result = services.initiate_payment(payment, gateway_slug=serializer.validated_data.get("gateway"), user=request.user)
        return Response(InitiateResultSerializer({"reference": result.reference, "redirect_url": result.redirect_url}).data)

    @extend_schema(
        tags=TAG, summary="Reconcile with the gateway",
        description="Asks the gateway directly for this payment's status, in case a webhook was missed.",
        responses={200: PaymentSerializer, 409: ERR},
    )
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        payment = self.get_object()
        services.verify_payment(payment, user=request.user)
        return self._detail(payment)

    @extend_schema(tags=TAG, summary="Record a refund", request=RefundInputSerializer, responses={201: PaymentSerializer, 400: ERR, 409: ERR})
    @action(detail=True, methods=["post"], url_path="refund")
    def refund(self, request, pk=None):
        payment = self.get_object()
        serializer = RefundInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.create_refund(payment, user=request.user, **serializer.validated_data)
        return self._detail(payment, status.HTTP_201_CREATED)
