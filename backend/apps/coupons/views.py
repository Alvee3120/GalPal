"""Public: apply or remove a coupon on the current cart (guest header token or logged-in customer,
exactly like the cart endpoints themselves — see apps.cart.views for the auth/permission story)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.cart import services as cart_services
from apps.cart.serializers import CartSerializer
from apps.cart.views import CART_TOKEN_PARAM, _cart_response
from apps.core.authentication import OptionalJWTAuthentication
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .serializers import ApplyCouponSerializer

ERR = OpenApiResponse(ErrorResponseSerializer)


class _CartCouponAPIView(APIView):
    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]


class CartCouponView(_CartCouponAPIView):
    """One resource, two verbs: POST attaches a coupon to the cart, DELETE detaches it."""

    @extend_schema(
        tags=["Coupons"], summary="Apply a coupon to the cart",
        description="Validates the code against the cart's current contents (min order, applicability, usage limits) and attaches it.",
        parameters=[CART_TOKEN_PARAM], request=ApplyCouponSerializer, responses={200: CartSerializer, 400: ERR},
    )
    def post(self, request):
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = cart_services.get_cart(request, create=True)
        try:
            services.apply_coupon_to_cart(cart, serializer.validated_data["code"], user=request.user)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from None
        return _cart_response(request, cart)

    @extend_schema(
        tags=["Coupons"], summary="Remove the cart's coupon",
        parameters=[CART_TOKEN_PARAM], responses={200: CartSerializer},
    )
    def delete(self, request):
        cart = cart_services.get_cart(request)
        if cart is not None:
            services.remove_coupon_from_cart(cart)
        return _cart_response(request, cart)
