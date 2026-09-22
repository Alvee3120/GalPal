from django.contrib import admin

from .models import Review, ReviewImage


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 0


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Fallback only; the real panel uses /api/v1/admin/reviews/ (which also recomputes the product's rating)."""

    list_display = ["product", "reviewer_name", "rating", "status", "is_verified_purchase", "is_manual", "created_at"]
    list_filter = ["status", "is_verified_purchase", "is_manual"]
    search_fields = ["reviewer_name", "text", "product__name"]
    inlines = [ReviewImageInline]
