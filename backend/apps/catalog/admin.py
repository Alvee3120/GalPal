from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import (
    AttributeValue,
    Brand,
    Category,
    Product,
    ProductAttribute,
    ProductCategory,
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


class ProductCategoryFormSet(BaseInlineFormSet):
    """
    Category picker for a product. The database allows exactly one primary category per product
    (a partial unique index), so this keeps that invariant: it rejects two primaries, and marks the
    first category primary when none is ticked. Primaries are reassigned in one step after saving,
    because moving the flag between two rows would otherwise trip the index part-way through.
    """

    def _live_forms(self):
        return [
            form for form in self.forms
            if form.cleaned_data.get("category") and not form.cleaned_data.get("DELETE")
        ]

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        if sum(1 for form in self._live_forms() if form.cleaned_data.get("is_primary")) > 1:
            raise ValidationError("Only one category can be the primary category.")

    def save(self, commit=True):
        if commit and self.instance.pk:
            # Clear first so the rows saved below can never collide with a stale primary flag.
            ProductCategory.objects.filter(product=self.instance, is_primary=True).update(is_primary=False)
        saved = super().save(commit)
        if commit:
            live = self._live_forms()
            if live:
                chosen = next((f for f in live if f.cleaned_data.get("is_primary")), live[0])
                ProductCategory.objects.filter(
                    product=self.instance, category=chosen.cleaned_data["category"]
                ).update(is_primary=True)
        return saved


class ProductCategoryInline(admin.TabularInline):
    model = ProductCategory
    formset = ProductCategoryFormSet
    extra = 1
    autocomplete_fields = ["category"]
    verbose_name = "category"
    verbose_name_plural = "categories (tick 'primary' on one; the first is primary if none is ticked)"


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
    prepopulated_fields = {"slug": ("name",)}  # fills itself in from the name while typing
    readonly_fields = ["average_rating", "review_count"]  # computed from reviews, never typed in
    inlines = [ProductCategoryInline, ProductImageInline, ProductVariantInline]

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
