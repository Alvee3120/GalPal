"""
Old carts for Admin + CCE (apps.cart.old_carts), mounted under /api/v1/admin/orders/ — the admin area a CCE may reach
(apps.accounts.permissions.CCE_ALLOWED_ADMIN_PREFIXES). IsAdminOrCCE: customers and guests get 401/403. Read-only.
"""

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrCCE

from . import old_carts, services
from .serializers import CartProductSerializer, CartVariantSerializer

TAG = ["Admin – Old Carts"]


class _Customer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(source="full_name")
    phone = serializers.CharField()
    email = serializers.EmailField(allow_null=True)


class OldCartRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    customer = _Customer(source="user")
    line_count = serializers.IntegerField(help_text="Products in the cart")
    old_line_count = serializers.IntegerField(help_text="Of which older than 6 hours")
    quantity = serializers.SerializerMethodField(help_text="Units in the cart")
    out_of_stock_count = serializers.SerializerMethodField(help_text="Products in the cart that are out of stock right now")
    cart_value = serializers.SerializerMethodField(help_text="Current value of the available items")
    oldest_item_at = serializers.DateTimeField()
    last_activity_at = serializers.DateTimeField()

    def _summary(self, cart):
        cache = self.context.setdefault("_summaries", {})
        if cart.pk not in cache:
            cache[cart.pk] = services.summarize(cart)
        return cache[cart.pk]

    def get_quantity(self, cart) -> int:
        return self._summary(cart)["item_count"]

    def get_out_of_stock_count(self, cart) -> int:
        return sum(1 for row in self._summary(cart)["rows"] if row["available_quantity"] is not None and row["available_quantity"] <= 0)

    def get_cart_value(self, cart) -> str:
        return f"{self._summary(cart)['subtotal']:.2f}"


class OldCartItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="item.id")
    product = CartProductSerializer(source="item.product")
    variant = CartVariantSerializer(source="item.variant", allow_null=True)
    quantity = serializers.IntegerField(source="item.quantity")
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Current price")
    line_total = serializers.SerializerMethodField(help_text="Quantity x current price")
    available_quantity = serializers.IntegerField(allow_null=True, help_text="Current stock; null = not tracked")
    in_stock = serializers.SerializerMethodField()
    added_at = serializers.DateTimeField(source="item.created_at")
    is_old = serializers.SerializerMethodField(help_text="In the cart for more than 6 hours")

    def get_line_total(self, row) -> str:
        return f"{row['unit_price'] * row['item'].quantity:.2f}"

    def get_in_stock(self, row) -> bool:
        cap = row["available_quantity"]
        return cap is None or cap > 0

    def get_is_old(self, row) -> bool:
        return old_carts.is_old(row["item"], self.context.get("now"))


@extend_schema(
    tags=TAG, summary="Old carts",
    description=(
        "Customers whose cart has held an item for more than 6 hours (`now - CartItem.created_at > 6h`), oldest "
        "first, one row per customer. `search` matches customer name, phone, email or a product name in the cart; "
        "`age` = `6_24` (6-24 hours) | `1_3` (1-3 days) | `3_plus` (3+ days), by the oldest item. Paginated like every "
        "admin list."
    ),
    parameters=[
        OpenApiParameter("search", str, required=False),
        OpenApiParameter("age", str, required=False, enum=list(old_carts.AGE_FILTERS)),
    ],
)
class OldCartListView(generics.ListAPIView):
    permission_classes = [IsAdminOrCCE]
    serializer_class = OldCartRowSerializer

    def get_queryset(self):
        params = self.request.query_params
        return old_carts.old_carts(search=params.get("search", ""), age=params.get("age", ""))

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if isinstance(response.data, dict):
            response.data["customers_with_old_carts"] = old_carts.customers_with_old_carts()
        return response


class OldCartDetailView(APIView):
    permission_classes = [IsAdminOrCCE]

    @extend_schema(tags=TAG, summary="Old cart details", responses={200: None})
    def get(self, request, pk):
        cart = old_carts.old_carts().filter(pk=pk).first()
        if cart is None:
            raise NotFound("No old cart with that id (it may have been checked out or emptied).")
        summary = services.summarize(cart)
        context = {"request": request, "now": None}
        return Response({
            "cart": OldCartRowSerializer(cart, context={**context, "_summaries": {cart.pk: summary}}).data,
            "items": OldCartItemSerializer(sorted(summary["rows"], key=lambda r: r["item"].created_at), many=True, context=context).data,
            "subtotal": f"{summary['subtotal']:.2f}",
        })
