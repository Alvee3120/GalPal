from django.contrib import admin

from .models import Brand, Category, Tag


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
