from django.contrib import admin

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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Fallback only; the real panel uses /api/v1/admin/categories/."""

    list_display = ["name", "parent", "is_active", "sort_order"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug"]
    raw_id_fields = ["parent"]


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    search_fields = ["name", "slug"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ["name", "slug"]


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    filter_horizontal = ["attribute_values"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Fallback only; the real panel uses /api/v1/admin/products/."""

    list_display = ["name", "sku", "status", "regular_price", "discount_price", "stock_quantity", "is_deleted"]
    list_filter = ["status", "is_featured", "is_new_arrival", "is_bestseller", "is_deleted"]
    search_fields = ["name", "sku", "barcode"]
    filter_horizontal = ["tags"]
    inlines = [ProductImageInline, ProductVariantInline]

    def get_queryset(self, request):
        return Product.all_objects.all()


@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    list_display = ["attribute", "value"]
    list_filter = ["attribute"]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ["product", "variant", "quantity_change", "balance_after", "reason", "created_at"]
    list_filter = ["reason"]
    raw_id_fields = ["product", "variant", "user"]
