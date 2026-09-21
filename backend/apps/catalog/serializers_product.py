"""Product, variant and inventory serializers (public storefront + admin)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.serializers import SlugSerializerMixin
from apps.core.utils import discard_file

from . import services
from .models import (
    AttributeValue,
    Brand,
    Category,
    Product,
    ProductAttribute,
    ProductImage,
    ProductVariant,
    StockMovement,
    Tag,
)
from .serializers import CategoryLinkSerializer, slug_field

# --- small nested read-only representations ------------------------------------------------


class BrandLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug"]
        read_only_fields = fields


class TagLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]
        read_only_fields = fields


class ProductCategoryLinkSerializer(serializers.Serializer):
    id = serializers.IntegerField(source="category.id")
    name = serializers.CharField(source="category.name")
    slug = serializers.CharField(source="category.slug")
    is_primary = serializers.BooleanField()


class AttributeValueLinkSerializer(serializers.ModelSerializer):
    attribute = serializers.CharField(source="attribute.name", read_only=True)
    attribute_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = AttributeValue
        fields = ["id", "attribute_id", "attribute", "value", "slug"]
        read_only_fields = fields


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "sort_order"]
        read_only_fields = ["id"]


# --- shared computed fields --------------------------------------------------------------


class _ComputedProductFields(serializers.Serializer):
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    on_sale = serializers.BooleanField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)


class VariantSerializer(_ComputedProductFields, serializers.ModelSerializer):
    attribute_values = AttributeValueLinkSerializer(many=True, read_only=True)
    regular_price = serializers.DecimalField(source="regular_price_effective", max_digits=12, decimal_places=2, read_only=True)
    discount_price = serializers.DecimalField(source="discount_price_effective", max_digits=12, decimal_places=2, read_only=True, allow_null=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id", "sku", "attribute_values", "regular_price", "discount_price",
            "effective_price", "discount_percentage", "on_sale", "stock_quantity",
            "manage_stock", "in_stock", "image", "is_active",
        ]
        read_only_fields = fields


# --- public --------------------------------------------------------------------------------


class PublicProductListSerializer(_ComputedProductFields, serializers.ModelSerializer):
    brand = BrandLinkSerializer(read_only=True)
    primary_category = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "feature_image", "brand", "primary_category",
            "regular_price", "discount_price", "effective_price", "discount_percentage", "on_sale",
            "sku", "in_stock", "has_variants", "is_featured", "is_new_arrival", "is_bestseller",
            "gender", "skin_type", "average_rating", "review_count",
        ]
        read_only_fields = fields

    @extend_schema_field(CategoryLinkSerializer)
    def get_primary_category(self, obj):
        link = next((link for link in obj.category_links.all() if link.is_primary), None)
        return CategoryLinkSerializer(link.category).data if link else None


class PublicProductDetailSerializer(PublicProductListSerializer):
    categories = ProductCategoryLinkSerializer(source="category_links", many=True, read_only=True)
    tags = TagLinkSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = serializers.SerializerMethodField()
    breadcrumb = serializers.SerializerMethodField()
    related_products = serializers.SerializerMethodField()

    class Meta(PublicProductListSerializer.Meta):
        fields = [
            *PublicProductListSerializer.Meta.fields,
            "short_description", "full_description", "user_guide",
            "sale_start_at", "sale_end_at",
            "categories", "tags", "images", "variants",
            "key_ingredients", "ingredients", "size_value", "size_unit", "country_of_origin",
            "manufacture_date", "expiry_date",
            "meta_title", "meta_description", "og_image",
            "breadcrumb", "related_products",
        ]
        read_only_fields = fields

    @extend_schema_field(VariantSerializer(many=True))
    def get_variants(self, obj):
        return VariantSerializer([v for v in obj.variants.all() if v.is_active], many=True, context=self.context).data

    @extend_schema_field(CategoryLinkSerializer(many=True))
    def get_breadcrumb(self, obj):
        link = next((link for link in obj.category_links.all() if link.is_primary), None)
        return self.context["index"].breadcrumb(link.category_id) if link and "index" in self.context else []

    @extend_schema_field(PublicProductListSerializer(many=True))
    def get_related_products(self, obj):
        return PublicProductListSerializer(
            self.context.get("related_products", []), many=True, context=self.context
        ).data


# --- admin: attributes -----------------------------------------------------------------------


class AdminAttributeValueSerializer(SlugSerializerMixin, serializers.ModelSerializer):
    slug = slug_field()
    slug_source = "value"

    class Meta:
        model = AttributeValue
        fields = ["id", "attribute", "value", "slug", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        validators = []

    def validate(self, attrs):
        attribute = attrs.get("attribute", self.instance.attribute if self.instance else None)
        value = attrs.get("value", self.instance.value if self.instance else None)
        clash = AttributeValue.objects.filter(attribute=attribute, value__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError({"value": ["This value already exists for the attribute."]})
        return super().validate(attrs)


class AdminProductAttributeSerializer(SlugSerializerMixin, serializers.ModelSerializer):
    slug = slug_field()
    values = AdminAttributeValueSerializer(many=True, read_only=True)

    class Meta:
        model = ProductAttribute
        fields = ["id", "name", "slug", "values", "created_at", "updated_at"]
        read_only_fields = ["id", "values", "created_at", "updated_at"]
        validators = []

    def validate_name(self, value):
        value = value.strip()
        queryset = ProductAttribute.objects.filter(name__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("An attribute with this name already exists.")
        return value


# --- admin: variants --------------------------------------------------------------------------


class AdminVariantSerializer(serializers.ModelSerializer):
    attribute_value_ids = serializers.PrimaryKeyRelatedField(
        source="attribute_values", queryset=AttributeValue.objects.all(), many=True, write_only=True
    )
    attribute_values = AttributeValueLinkSerializer(many=True, read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id", "sku", "attribute_value_ids", "attribute_values", "regular_price", "discount_price",
            "stock_quantity", "manage_stock", "image", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "stock_quantity", "created_at", "updated_at"]

    def validate_sku(self, value):
        services.assert_unique_sku(value, exclude_variant=self.instance)
        return value

    def validate(self, attrs):
        regular = attrs.get("regular_price", self.instance.regular_price if self.instance else None)
        discount = attrs.get("discount_price", self.instance.discount_price if self.instance else None)
        if regular is not None and discount is not None and discount >= regular:
            raise serializers.ValidationError({"discount_price": ["Must be less than the regular price."]})
        return attrs

    def create(self, validated_data):
        attribute_values = validated_data.pop("attribute_values")
        validated_data["product"] = self.context["product"]
        with transaction.atomic():
            variant = ProductVariant.objects.create(**validated_data)
            try:
                services.set_variant_options(variant, [v.pk for v in attribute_values])
            except DjangoValidationError as exc:
                raise serializers.ValidationError(exc.message_dict) from None
        return variant

    def update(self, instance, validated_data):
        attribute_values = validated_data.pop("attribute_values", None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            if attribute_values is not None:
                try:
                    services.set_variant_options(instance, [v.pk for v in attribute_values])
                except DjangoValidationError as exc:
                    raise serializers.ValidationError(exc.message_dict) from None
        return instance


# --- admin: gallery images ---------------------------------------------------------------------


class AdminProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "sort_order", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        validated_data["product"] = self.context["product"]
        return super().create(validated_data)


# --- admin: product ----------------------------------------------------------------------------


class AdminProductSerializer(SlugSerializerMixin, serializers.ModelSerializer):
    slug = slug_field()
    category_ids = serializers.PrimaryKeyRelatedField(
        source="categories", queryset=Category.objects.all(), many=True, required=False, write_only=True
    )
    primary_category_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    tag_ids = serializers.PrimaryKeyRelatedField(source="tags", queryset=Tag.objects.all(), many=True, required=False, write_only=True)

    categories = ProductCategoryLinkSerializer(source="category_links", many=True, read_only=True)
    tags = TagLinkSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = VariantSerializer(many=True, read_only=True)

    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    on_sale = serializers.BooleanField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "short_description", "full_description", "user_guide",
            "feature_image", "images",
            "category_ids", "primary_category_id", "categories", "tag_ids", "tags", "brand",
            "regular_price", "discount_price", "sale_start_at", "sale_end_at",
            "effective_price", "discount_percentage", "on_sale",
            "sku", "barcode", "stock_quantity", "manage_stock", "low_stock_threshold", "stock_status",
            "in_stock", "is_low_stock", "has_variants", "variants",
            "skin_type", "key_ingredients", "ingredients", "size_value", "size_unit",
            "country_of_origin", "manufacture_date", "expiry_date", "gender",
            "is_featured", "is_new_arrival", "is_bestseller", "status",
            "meta_title", "meta_description", "og_image",
            "average_rating", "review_count", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "images", "categories", "tags", "stock_quantity", "stock_status", "variants",
            "average_rating", "review_count", "created_at", "updated_at",
        ]
        validators = []

    def validate_sku(self, value):
        services.assert_unique_sku(value, exclude_product=self.instance)
        return value

    def validate(self, attrs):
        # NB: must chain to SlugSerializerMixin.validate(), which computes attrs["slug"] /
        # attrs["slug_is_custom"] — skipping it silently leaves the product with a blank slug.
        attrs = super().validate(attrs)
        regular = attrs.get("regular_price", self.instance.regular_price if self.instance else None)
        discount = attrs.get("discount_price", self.instance.discount_price if self.instance else None)
        if discount is not None and regular is not None and discount >= regular:
            raise serializers.ValidationError({"discount_price": ["Must be less than the regular price."]})
        return attrs

    def _save_categories(self, product, validated_data):
        if "categories" not in validated_data and "primary_category_id" not in validated_data:
            return
        category_ids = [c.pk for c in validated_data.pop("categories", None) or (product.categories.all() if self.instance else [])]
        primary_id = validated_data.pop("primary_category_id", None)
        try:
            services.set_categories(product, category_ids, primary_id)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from None

    def create(self, validated_data):
        tags = validated_data.pop("tags", [])
        with transaction.atomic():
            categories_kwargs = {
                k: validated_data.pop(k) for k in ("categories", "primary_category_id") if k in validated_data
            }
            product = Product.objects.create(**validated_data)
            product.tags.set(tags)
            self._save_categories(product, categories_kwargs)
        return product

    def update(self, instance, validated_data):
        tags = validated_data.pop("tags", None)
        categories_kwargs = {
            k: validated_data.pop(k) for k in ("categories", "primary_category_id") if k in validated_data
        }
        with transaction.atomic():
            old_feature, old_og = instance.feature_image, instance.og_image
            instance = super().update(instance, validated_data)
            if tags is not None:
                instance.tags.set(tags)
            self._save_categories(instance, categories_kwargs)
            for old, field in ((old_feature, "feature_image"), (old_og, "og_image")):
                current = getattr(instance, field)
                if old and old.name and (not current or current.name != old.name):
                    discard_file(old)
        return instance


class AdminProductListSerializer(AdminProductSerializer):
    """Lighter shape for the list endpoint (no nested images/variants/category detail)."""

    class Meta(AdminProductSerializer.Meta):
        fields = [
            "id", "name", "slug", "feature_image", "brand", "sku", "regular_price", "discount_price",
            "effective_price", "stock_quantity", "stock_status", "in_stock", "is_low_stock",
            "status", "is_featured", "is_new_arrival", "is_bestseller", "has_variants",
            "average_rating", "review_count", "created_at", "updated_at",
        ]
        read_only_fields = fields


# --- admin: bulk actions & stock ---------------------------------------------------------------


class BulkIdsSerializer(serializers.Serializer):
    product_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, min_length=1, max_length=500)


class StockAdjustmentSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False)
    variant_id = serializers.IntegerField(required=False)
    quantity_change = serializers.IntegerField(help_text="Positive to add stock, negative to remove.")
    reason = serializers.ChoiceField(choices=StockMovement.Reason.choices)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=100)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        if bool(attrs.get("product_id")) == bool(attrs.get("variant_id")):
            raise serializers.ValidationError("Provide exactly one of product_id or variant_id.")
        if attrs["quantity_change"] == 0:
            raise serializers.ValidationError({"quantity_change": ["Must not be zero."]})
        return attrs


class BulkStockUpdateSerializer(serializers.Serializer):
    items = StockAdjustmentSerializer(many=True, allow_empty=False, max_length=500)


class StockMovementSerializer(serializers.ModelSerializer):
    product = serializers.CharField(source="product.name", read_only=True)
    variant_sku = serializers.CharField(source="variant.sku", read_only=True, allow_null=True)
    user = serializers.CharField(source="user.full_name", read_only=True, allow_null=True)

    class Meta:
        model = StockMovement
        fields = [
            "id", "product", "variant_sku", "quantity_change", "balance_after",
            "reason", "reference", "note", "user", "created_at",
        ]
        read_only_fields = fields


class ProductPickerSerializer(serializers.ModelSerializer):
    """Lightweight product shape for admin dropdowns/search widgets (e.g. picking videos' products)."""

    class Meta:
        model = Product
        fields = ["id", "name", "sku", "feature_image"]
        read_only_fields = fields
