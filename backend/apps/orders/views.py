"""Storefront order endpoints: checkout, the customer's own orders (list, detail, cancel) and guest tracking."""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsOwner
from apps.cart import services as cart_services
from apps.cart.views import CART_TOKEN_PARAM
from apps.core.authentication import OptionalJWTAuthentication
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .models import Order
from .serializers import (
    CancelOrderSerializer,
    CheckoutResultSerializer,
    CheckoutSerializer,
    OrderListSerializer,
    PublicOrderSerializer,
    TrackedOrderSerializer,
    TrackOrderSerializer,
)
from .throttles import CheckoutThrottle, TrackOrderThrottle

ERR = OpenApiResponse(ErrorResponseSerializer)
TAG = ["Checkout & Orders"]


def _fresh(order_id):
    return Order.objects.prefetch_related("items", "history").get(pk=order_id)


class CheckoutView(APIView):
    authentication_classes = [OptionalJWTAuthentication]  # a stale token means "guest", not a 401
    permission_classes = [AllowAny]
    throttle_classes = [CheckoutThrottle]

    @extend_schema(
        tags=TAG, summary="Place an order from the cart",
        description=(
            "Customer or guest. The items come from the cart (login, or the `X-Cart-Token` header). "
            "The server computes every amount: prices, the coupon discount, the delivery charge (from the address's "
            "district/area and Module 9's zones), tax and the total. The client cannot send a charge, and `source` is "
            "always `website`.\n\n"
            "Guests: 403 `guest_checkout_disabled` if the store turned guest checkout off. With `save_details=true` "
            "(and the store allowing it) an `email` is required and an account is created and emailed a generated "
            "password after the order commits; `account_created` says whether that happened. If the phone or email "
            "already has an account, the order is placed as a normal guest order and nothing reveals that.\n\n"
            "409 `duplicate_order`: the same phone and items were just ordered. 429: too many orders."
        ),
        parameters=[CART_TOKEN_PARAM], request=CheckoutSerializer,
        responses={201: CheckoutResultSerializer, 400: ERR, 403: ERR, 409: ERR, 429: ERR},
    )
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user if request.user.is_authenticated else None
        cart = cart_services.get_cart(request)
        placed = services.checkout(
            cart=cart, user=user, data=serializer.validated_data, ip_address=request.META.get("REMOTE_ADDR")
        )
        body = {"order": PublicOrderSerializer(_fresh(placed.order.pk), context={"request": request}).data,
                "account_created": placed.account_created}
        return Response(body, status=status.HTTP_201_CREATED)


class TrackOrderView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [TrackOrderThrottle]

    @extend_schema(
        tags=TAG, summary="Track a guest order",
        description="Order number + the phone it was placed with. A wrong number or a wrong phone gives the same 404, so it can't be used to probe which numbers exist.",
        request=TrackOrderSerializer, responses={200: TrackedOrderSerializer, 404: ERR, 429: ERR},
    )
    def post(self, request):
        serializer = TrackOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.find_for_tracking(serializer.validated_data["order_number"], serializer.validated_data["phone"])
        if order is None:
            raise NotFound("No order matches that number and phone.")
        return Response(TrackedOrderSerializer(order, context={"request": request}).data)


class MyOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The logged-in customer's own orders, looked up by order number."""

    permission_classes = [IsAuthenticated, IsOwner]
    owner_field = "customer"
    lookup_field = "number"
    lookup_value_regex = r"[A-Za-z0-9-]+"
    filterset_fields = ["status"]
    ordering = ["-created_at", "-id"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return Order.objects.filter(customer=self.request.user).prefetch_related("items", "history")

    def get_serializer_class(self):
        return OrderListSerializer if self.action == "list" else PublicOrderSerializer

    def get_object(self):
        # Numbers are case-insensitive to a human typing one.
        self.kwargs[self.lookup_field] = self.kwargs[self.lookup_field].upper()
        return super().get_object()

    @extend_schema(tags=TAG, summary="List my orders")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(tags=TAG, summary="My order detail", responses={200: PublicOrderSerializer, 404: ERR})
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=TAG, summary="Cancel my order",
        description="Only while the order is `pending` or `confirmed`; stock is put back and the coupon released. 409 `not_cancellable` otherwise.",
        request=CancelOrderSerializer, responses={200: PublicOrderSerializer, 404: ERR, 409: ERR},
    )
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, number=None):
        order = self.get_object()
        serializer = CancelOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.cancel_by_customer(order, request.user, serializer.validated_data.get("note", ""))
        return Response(PublicOrderSerializer(_fresh(order.pk), context={"request": request}).data)
