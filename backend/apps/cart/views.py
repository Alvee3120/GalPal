"""
Storefront cart endpoints. Open to guests and logged-in customers alike: a guest identifies
their cart with the `X-Cart-Token` header (see `services.CART_TOKEN_HEADER`), a logged-in
customer just needs their access token. `merge_guest_cart_into_user` folds a guest cart into the
account's cart right after login/registration (see `apps.accounts.views`).
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import OptionalJWTAuthentication
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .models import CartItem
from .serializers import AddCartItemSerializer, CartSerializer, SetCartItemQuantitySerializer

ERR = OpenApiResponse(ErrorResponseSerializer)
CART_TOKEN_PARAM = OpenApiParameter(
    "X-Cart-Token", str, OpenApiParameter.HEADER,
    description="Guest cart id, returned by this API's first response to a guest. Omit once logged in.",
)


def _raise(exc):
    raise ValidationError(exc.message_dict) from None


def _cart_response(request, cart, *, status=200):
    data = {**services.summarize(cart), "cart_token": cart.token if cart else None}
    response = Response(CartSerializer(data, context={"request": request}).data, status=status)
    if cart is not None and cart.token is not None:
        response[services.CART_TOKEN_HEADER] = str(cart.token)
    return response


class _CartAPIView(APIView):
    # A valid access token identifies the logged-in customer's cart; an invalid/expired/absent one
    # is simply anonymous (a guest), never a 401 — see OptionalJWTAuthentication's docstring.
    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]


@extend_schema(
    tags=["Cart"], summary="Get the current cart",
    description="A guest with no (valid) X-Cart-Token, or one who has never added anything, gets an empty cart with no token.",
    parameters=[CART_TOKEN_PARAM], responses=CartSerializer,
)
class CartView(_CartAPIView):
    def get(self, request):
        return _cart_response(request, services.get_cart(request))


@extend_schema(
    tags=["Cart"], summary="Add an item to the cart",
    description=(
        "Adds `quantity` more of a product (or variant, if the product has variants) — if it's "
        "already in the cart, the quantity is increased, not replaced (use PATCH on the item to "
        "set an absolute quantity). A guest's first add creates their cart: read the new "
        "`cart_token` from the response body (or the `X-Cart-Token` response header) and send it "
        "back on every later request."
    ),
    parameters=[CART_TOKEN_PARAM], request=AddCartItemSerializer, responses={200: CartSerializer, 400: ERR},
)
class CartItemListView(_CartAPIView):
    def post(self, request):
        serializer = AddCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = services.get_cart(request, create=True)
        try:
            services.add_item(cart, **serializer.validated_data)
        except DjangoValidationError as exc:
            _raise(exc)
        return _cart_response(request, cart)


class _CartItemAPIView(_CartAPIView):
    def get_item(self, request, item_id):
        cart = services.get_cart(request)
        item = CartItem.objects.filter(pk=item_id, cart=cart).first() if cart else None
        if item is None:
            raise NotFound("Cart item not found.")
        return cart, item


@extend_schema(
    tags=["Cart"], summary="Set a cart item's quantity",
    description="Sets the line to exactly this quantity (0 is rejected — DELETE the item instead).",
    parameters=[CART_TOKEN_PARAM], request=SetCartItemQuantitySerializer, responses={200: CartSerializer, 400: ERR, 404: ERR},
)
class CartItemDetailView(_CartItemAPIView):
    def patch(self, request, item_id):
        cart, item = self.get_item(request, item_id)
        serializer = SetCartItemQuantitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.set_item_quantity(item, serializer.validated_data["quantity"])
        except DjangoValidationError as exc:
            _raise(exc)
        return _cart_response(request, cart)

    @extend_schema(
        tags=["Cart"], summary="Remove a cart item",
        parameters=[CART_TOKEN_PARAM], responses={200: CartSerializer, 404: ERR},
    )
    def delete(self, request, item_id):
        cart, item = self.get_item(request, item_id)
        services.remove_item(item)
        return _cart_response(request, cart)
