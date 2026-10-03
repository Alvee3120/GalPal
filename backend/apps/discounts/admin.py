from django.contrib import admin

from .models import Discount


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "value", "target_type", "category", "starts_at", "ends_at", "is_active"]
    list_filter = ["kind", "target_type", "is_active"]
    search_fields = ["name"]
    filter_horizontal = ["products"]
