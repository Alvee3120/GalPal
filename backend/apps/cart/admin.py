from django.contrib import admin

from .models import Cart, CartItem, WishlistItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    raw_id_fields = ["product", "variant"]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "token", "created_at"]
    search_fields = ["user__phone", "user__full_name"]
    raw_id_fields = ["user"]
    inlines = [CartItemInline]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "product", "created_at"]
    search_fields = ["user__phone", "user__full_name", "product__name"]
    raw_id_fields = ["user", "product"]
