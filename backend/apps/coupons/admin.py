from django.contrib import admin

from .models import Coupon, CouponUsage


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["code", "type", "amount", "is_active", "expiry_at"]
    list_filter = ["is_active", "type"]
    search_fields = ["code"]
    filter_horizontal = ["products", "categories", "brands"]


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ["coupon", "phone", "order_reference", "discount_amount", "created_at"]
    raw_id_fields = ["coupon", "user"]
