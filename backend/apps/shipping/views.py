"""Public shipping endpoints: zones, methods, districts and the delivery-charge calculator."""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart import services as cart_services
from apps.cart.views import CART_TOKEN_PARAM
from apps.core.authentication import OptionalJWTAuthentication
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .models import District
from .serializers import (
    CalculateShippingSerializer,
    DistrictSerializer,
    PublicMethodSerializer,
    PublicZoneSerializer,
    ShippingQuoteSerializer,
)

ERR = OpenApiResponse(ErrorResponseSerializer)


class _PublicView(APIView):
    authentication_classes = []  # a stale token must not break a public page
    permission_classes = [AllowAny]


class ZoneListView(_PublicView):
    @extend_schema(
        tags=["Shipping"], summary="List delivery zones",
        description=(
            "Active zones with their charge and delivery estimate, in display order. Not paginated (it is a short list). "
            "`free_shipping_threshold` is the subtotal that makes delivery free in that zone."
        ),
        responses=PublicZoneSerializer(many=True),
    )
    def get(self, request):
        return Response(PublicZoneSerializer(services.public_zones(), many=True).data)


class MethodListView(_PublicView):
    @extend_schema(
        tags=["Shipping"], summary="List delivery methods",
        description="Active delivery methods (Standard, Express...) with the extra charge each adds to the zone charge. Empty until the Admin enables one.",
        responses=PublicMethodSerializer(many=True),
    )
    def get(self, request):
        return Response(PublicMethodSerializer(services.public_methods(), many=True).data)


class DistrictListView(_PublicView):
    @extend_schema(
        tags=["Shipping"], summary="List Bangladesh's 64 districts",
        description="For the checkout address form. Not paginated.",
        responses=DistrictSerializer(many=True),
    )
    def get(self, request):
        return Response(DistrictSerializer(District.objects.all(), many=True).data)


class CalculateShippingView(APIView):
    authentication_classes = [OptionalJWTAuthentication]  # same guest/customer identity as the cart
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Shipping"], summary="Calculate the delivery charge",
        description=(
            "Resolves the zone from `district` (and `area`), adds the chosen method's extra, and applies the free-shipping "
            "rules: the subtotal reaching the zone's (or the global) threshold, or the cart's coupon granting free shipping. "
            "Send `subtotal`, or omit it to use the current cart (`X-Cart-Token` / login), whose valid coupon is then considered. "
            "This is a preview: checkout recomputes it on the server and never accepts a client-sent charge."
        ),
        parameters=[CART_TOKEN_PARAM], request=CalculateShippingSerializer,
        responses={200: ShippingQuoteSerializer, 400: ERR},
    )
    def post(self, request):
        serializer = CalculateShippingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        subtotal = data.get("subtotal")
        coupon = None
        cart = cart_services.get_cart(request)
        if cart is not None:
            summary = cart_services.summarize(cart)
            if summary["coupon"] and summary["coupon"]["is_valid"]:
                coupon = cart.coupon
            if subtotal is None:
                subtotal = summary["subtotal"]
        if subtotal is None:
            raise ValidationError({"subtotal": ["Send a subtotal, or your cart token / login so the cart can be used."]})

        quote = services.calculate_shipping(
            {"district": data["district"], "area": data["area"]}, subtotal, coupon,
            delivery_method=data["delivery_method"] or None,
        )
        return Response(ShippingQuoteSerializer(quote).data)
