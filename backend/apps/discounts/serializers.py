from rest_framework import serializers

from apps.catalog.models import Category, Product

from . import services
from .models import Discount, DiscountKind, DiscountTarget


class DiscountProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "sku", "feature_image", "regular_price", "stock_quantity", "stock_status", "status"]
        read_only_fields = fields


class AdminDiscountSerializer(serializers.ModelSerializer):
    """
    Admin create / edit. The backend decides everything: value range per type, end after start, the categories or the
    products exist, and a fixed amount isn't larger than the price of any product (or active variant) it covers now.
    """

    category_ids = serializers.PrimaryKeyRelatedField(source="categories", queryset=Category.objects.all(), many=True, required=False)
    categories = serializers.SerializerMethodField()
    product_ids = serializers.PrimaryKeyRelatedField(source="products", queryset=Product.objects.all(), many=True, required=False)
    products = DiscountProductSerializer(many=True, read_only=True)
    product_count = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    created_by = serializers.CharField(source="created_by.full_name", read_only=True, default=None)

    class Meta:
        model = Discount
        fields = [
            "id", "name", "kind", "value", "target_type", "category_ids", "categories", "product_ids", "products",
            "product_count", "starts_at", "ends_at", "is_active", "status", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "categories", "products", "product_count", "status", "created_by", "created_at", "updated_at"]

    def get_categories(self, obj) -> list[dict]:
        return [{"id": c.id, "name": c.name, "slug": c.slug} for c in obj.categories.all()]

    def get_product_count(self, obj) -> int:
        """Products this discount covers right now (a category counts its products, sub-categories included)."""
        if obj.target_type == DiscountTarget.PRODUCTS:
            return len(obj.products.all())
        return len(services.target_product_ids(obj))

    def get_status(self, obj) -> str:
        return services.status_of(obj)

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("Give the discount a name.", code="required")
        return value

    def validate(self, attrs):
        get = lambda key: attrs.get(key, getattr(self.instance, key, None))  # noqa: E731 - PATCH falls back to the saved value
        kind, value, target = get("kind"), get("value"), get("target_type")
        starts, ends = get("starts_at"), get("ends_at")
        errors = {}

        if value is not None and value <= 0:
            errors["value"] = "The discount must be more than 0."
        elif kind == DiscountKind.PERCENTAGE and value is not None and value > 100:
            errors["value"] = "A percentage can't be more than 100."
        if starts and ends and ends <= starts:
            errors["ends_at"] = "The end must be after the start."

        if target == DiscountTarget.CATEGORY:
            categories = attrs.get("categories")
            if categories is None and self.instance is not None:
                categories = list(self.instance.categories.all())
            if not categories:
                errors["category_ids"] = "Choose at least one category."
            attrs["products"] = []  # a category discount has no product list
        elif target == DiscountTarget.PRODUCTS:
            products = attrs.get("products")
            if products is None and self.instance is not None:
                products = list(self.instance.products.all())
            products = [p for p in (products or []) if not getattr(p, "is_deleted", False)]
            if not products:
                errors["product_ids"] = "Choose at least one product."
            elif "products" in attrs:
                attrs["products"] = products
            attrs["categories"] = []  # and a product discount no categories

        if errors:
            raise serializers.ValidationError(errors)

        if kind == DiscountKind.FIXED and value is not None:
            if target == DiscountTarget.PRODUCTS:
                ids = {p.pk for p in (attrs.get("products") or (self.instance.products.all() if self.instance else []))}
            else:
                categories = attrs.get("categories")
                if categories is None and self.instance is not None:
                    categories = list(self.instance.categories.all())
                ids = services.category_product_ids(c.pk for c in categories or [])
            too_cheap = services.items_priced_below(ids, value)
            if too_cheap:
                raise serializers.ValidationError({"value": (
                    f"{value} off is more than the price of: {', '.join(too_cheap)}. Lower the amount or use a percentage."
                )})
        return attrs
