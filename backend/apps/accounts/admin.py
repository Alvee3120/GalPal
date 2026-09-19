from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Fallback only: the real admin panel is the Next.js app using /api/v1/admin/."""

    ordering = ["-created_at"]
    list_display = ["phone", "full_name", "email", "role", "is_active", "created_via_checkout"]
    list_filter = ["role", "is_active", "created_via_checkout"]
    search_fields = ["phone", "full_name", "email"]
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Profile", {"fields": ("full_name", "email", "avatar")}),
        ("Access", {"fields": ("role", "is_active", "created_via_checkout", "must_change_password")}),
        ("Dates", {"fields": ("last_login", "created_at")}),
    )
    readonly_fields = ["last_login", "created_at"]
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "full_name", "role", "password1", "password2")}),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["user", "label", "district", "is_default"]
    search_fields = ["user__phone", "full_name", "district"]
    raw_id_fields = ["user"]
