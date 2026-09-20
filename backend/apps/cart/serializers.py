from rest_framework import serializers

from apps.catalog.serializers_product import AttributeValueLinkSerializer

# --- read -------------------------------------------------------------------------------------


class CartProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    sku = serializers.CharField()
    feature_image = serializers.ImageField()


class CartVariantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    sku = serializers.CharField()
    attribute_values = AttributeValueLinkSerializer(many=True)


class CartItemSerializer(serializers.Serializer):
    """
    One cart line, built from a `services.summarize()` row (`{item, unit_price, line_total,
    is_available, available_quantity}`), not straight from the `CartItem` model: the price and
    availability are computed live and don't exist as attributes on the row itself.
    """

    id = serializers.IntegerField(source="item.id")
    product = CartProductSerializer(source="item.product")
    variant = CartVariantSerializer(source="item.variant", allow_null=True)
    quantity = serializers.IntegerField(source="item.quantity")
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    is_available = serializers.BooleanField()
    available_quantity = serializers.IntegerField(allow_null=True)


class ShippingEstimateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    note = serializers.CharField()


class AppliedCouponSerializer(serializers.Serializer):
    code = serializers.CharField()
    is_valid = serializers.BooleanField()
    message = serializers.CharField()


class CartSerializer(serializers.Serializer):
    """
    The full cart, built from `{**services.summarize(cart), "cart_token": ...}`.
    `cart_token` is present only for a guest cart the client should remember and resend.
    """

    cart_token = serializers.UUIDField(allow_null=True)
    items = CartItemSerializer(source="rows", many=True)
    item_count = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    coupon = AppliedCouponSerializer(allow_null=True)
    shipping = ShippingEstimateSerializer()
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


# --- write ------------------------------------------------------------------------------------


class AddCartItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, max_value=999, default=1)


class SetCartItemQuantitySerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1, max_value=999)
