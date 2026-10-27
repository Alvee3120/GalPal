from rest_framework import serializers

from apps.catalog.models import Category, Product

from . import services
from .models import (
    CART_KINDS,
    PRODUCT_KINDS,
    Discount,
    DiscountKind,
    DiscountTarget,
    promotion_label,
)


class DiscountProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "sku", "feature_image", "regular_price", "stock_quantity", "stock_status", "status"]
        read_only_fields = fields


class AdminDiscountSerializer(serializers.ModelSerializer):
    """
    Admin create / edit. The backend decides everything: the fields each kind needs, end after start, the categories or
    the products exist, and a fixed amount isn't larger than the price of any product (or active variant) it covers now.
    """

    category_ids = serializers.PrimaryKeyRelatedField(source="categories", queryset=Category.objects.all(), many=True, required=False)
    categories = serializers.SerializerMethodField()
    product_ids = serializers.PrimaryKeyRelatedField(source="products", queryset=Product.objects.all(), many=True, required=False)
    products = DiscountProductSerializer(many=True, read_only=True)
    product_count = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    created_by = serializers.CharField(source="created_by.full_name", read_only=True, default=None)
    value = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)

    class Meta:
        model = Discount
        fields = [
            "id", "name", "kind", "value", "target_type", "category_ids", "categories", "product_ids", "products",
            "product_count", "label", "min_quantity", "percent_off", "free_quantity", "bundle_price", "same_product_group",
            "allow_repeat", "priority", "starts_at", "ends_at", "is_active", "status", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "categories", "products", "product_count", "label", "status", "created_by", "created_at", "updated_at"]

    def get_categories(self, obj) -> list[dict]:
        return [{"id": c.id, "name": c.name, "slug": c.slug} for c in obj.categories.all()]

    def get_product_count(self, obj) -> int:
        """Products this discount covers right now (a category counts its products, sub-categories included)."""
        if obj.target_type == DiscountTarget.PRODUCTS:
            return len(obj.products.all())
        return len(services.target_product_ids(obj))

    def get_label(self, obj) -> str:
        return promotion_label(obj)

    def get_status(self, obj) -> str:
        return services.status_of(obj)

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("Give the discount a name.", code="required")
        return value

    def validate(self, attrs):
        get = lambda key: attrs.get(key, getattr(self.instance, key, None))  # noqa: E731 - PATCH falls back to the saved value
        kind, target = get("kind"), get("target_type")
        starts, ends = get("starts_at"), get("ends_at")
        errors = {}

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

        if kind in PRODUCT_KINDS:
            value = get("value")
            if value is None or value <= 0:
                errors["value"] = "The discount must be more than 0."
            elif kind == DiscountKind.PERCENTAGE and value > 100:
                errors["value"] = "A percentage can't be more than 100."
            # a product price discount has no cart configuration
            attrs.update(min_quantity=None, percent_off=None, free_quantity=None, bundle_price=None)
        elif kind in CART_KINDS:
            attrs["value"] = None  # a cart promotion prices no single product
            errors.update(self._validate_cart(attrs, get, kind))

        if errors:
            raise serializers.ValidationError(errors)

        if kind == DiscountKind.FIXED and get("value") is not None:
            if target == DiscountTarget.PRODUCTS:
                ids = {p.pk for p in (attrs.get("products") or (self.instance.products.all() if self.instance else []))}
            else:
                categories = attrs.get("categories")
                if categories is None and self.instance is not None:
                    categories = list(self.instance.categories.all())
                ids = services.category_product_ids(c.pk for c in categories or [])
            too_cheap = services.items_priced_below(ids, get("value"))
            if too_cheap:
                raise serializers.ValidationError({"value": (
                    f"{get('value')} off is more than the price of: {', '.join(too_cheap)}. Lower the amount or use a percentage."
                )})
        return attrs

    def _validate_cart(self, attrs, get, kind):
        """Per-kind required fields for a cart promotion; also blanks the configuration it doesn't use."""
        errors = {}
        # Read the submitted/saved values FIRST — we clear the unused ones below, so reading them back through `get`
        # afterwards would only ever see the cleared None.
        min_quantity = get("min_quantity")
        percent_off = get("percent_off")
        free_quantity = get("free_quantity")
        bundle_price = get("bundle_price")

        # Start from "nothing set", then turn on only what this kind needs.
        attrs.update(percent_off=None, free_quantity=None, bundle_price=None)

        def require_quantity():
            if min_quantity is None or min_quantity < 1:
                errors["min_quantity"] = "Enter how many items are needed (at least 1)."
            else:
                attrs["min_quantity"] = min_quantity

        if kind == DiscountKind.BUY_X_GET_Y_PERCENT:
            require_quantity()
            if percent_off is None or percent_off <= 0:
                errors["percent_off"] = "The percentage must be more than 0."
            elif percent_off > 100:
                errors["percent_off"] = "A percentage can't be more than 100."
            else:
                attrs["percent_off"] = percent_off
        elif kind == DiscountKind.BUY_X_GET_Y_FREE:
            require_quantity()
            if free_quantity is None or free_quantity < 1:
                errors["free_quantity"] = "Enter how many items are free (at least 1)."
            else:
                attrs["free_quantity"] = free_quantity
        elif kind == DiscountKind.LOWEST_FREE:
            require_quantity()
        elif kind == DiscountKind.BUNDLE_PRICE:
            require_quantity()
            if bundle_price is None or bundle_price <= 0:
                errors["bundle_price"] = "Enter the bundle price (more than 0)."
            else:
                attrs["bundle_price"] = bundle_price
        elif kind == DiscountKind.THREE_FOR_TWO:
            attrs["min_quantity"] = None  # 3 for 2 has fixed quantities (3 buy, 1 free)
        return errors
