from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.catalog.models import Brand, Category, Product
from apps.catalog.serializers import CategoryLinkSerializer
from apps.catalog.serializers_product import BrandLinkSerializer, ProductPickerSerializer

from .models import Coupon, CouponType, CouponUsage

# --- apply/remove on the cart -------------------------------------------------------------------


class ApplyCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32)


# --- admin: coupon CRUD --------------------------------------------------------------------------


class AdminCouponSerializer(serializers.ModelSerializer):
    product_ids = serializers.PrimaryKeyRelatedField(
        source="products", queryset=Product.objects.all(), many=True, required=False, write_only=True
    )
    category_ids = serializers.PrimaryKeyRelatedField(
        source="categories", queryset=Category.objects.all(), many=True, required=False, write_only=True
    )
    brand_ids = serializers.PrimaryKeyRelatedField(
        source="brands", queryset=Brand.objects.all(), many=True, required=False, write_only=True
    )
    products = ProductPickerSerializer(many=True, read_only=True)
    categories = CategoryLinkSerializer(many=True, read_only=True)
    brands = BrandLinkSerializer(many=True, read_only=True)

    usage_count = serializers.SerializerMethodField()

    class Meta:
        model = Coupon
        fields = [
            "id", "code", "description", "type", "amount", "max_discount_amount", "min_order_amount",
            "start_at", "expiry_at", "is_active", "total_usage_limit", "per_customer_usage_limit",
            "product_ids", "products", "category_ids", "categories", "brand_ids", "brands",
            "exclude_sale_items", "first_order_only", "free_shipping", "usage_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "products", "categories", "brands", "usage_count", "created_at", "updated_at"]
        validators = []  # `validate_code` below does the (case-insensitive) uniqueness check

    def get_usage_count(self, obj) -> int:
        return obj.usages.count()

    def validate_code(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        queryset = Coupon.objects.filter(code=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A coupon with this code already exists.")
        return value

    def validate(self, attrs):
        coupon_type = attrs.get("type", self.instance.type if self.instance else None)
        amount = attrs.get("amount", self.instance.amount if self.instance else None)
        max_discount = attrs.get("max_discount_amount", self.instance.max_discount_amount if self.instance else None)
        start_at = attrs.get("start_at", self.instance.start_at if self.instance else None)
        expiry_at = attrs.get("expiry_at", self.instance.expiry_at if self.instance else None)

        errors = {}
        if coupon_type == CouponType.PERCENTAGE and amount is not None and amount > 100:
            errors["amount"] = ["A percentage coupon cannot exceed 100."]
        if coupon_type == CouponType.FLAT and max_discount is not None:
            errors["max_discount_amount"] = ["Only applies to percentage coupons."]
        if start_at and expiry_at and expiry_at <= start_at:
            errors["expiry_at"] = ["Must be after the start date."]
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class CouponUsageSerializer(serializers.ModelSerializer):
    coupon_code = serializers.CharField(source="coupon.code", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True, allow_null=True)

    class Meta:
        model = CouponUsage
        fields = ["id", "coupon_code", "user_name", "phone", "order_reference", "discount_amount", "created_at"]
        read_only_fields = fields
