from django.contrib import admin

from .models import DeliveryMethod, DeliveryZone, District, ShippingChargeHistory, ZoneDistrict


class ZoneDistrictInline(admin.TabularInline):
    model = ZoneDistrict
    extra = 0
    autocomplete_fields = ["district"]


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    """Fallback only; the real panel uses /api/v1/admin/shipping/zones/ (which also writes the charge history)."""

    list_display = ["name", "charge", "free_shipping_threshold", "is_active", "is_default", "sort_order"]
    list_filter = ["is_active", "is_default"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ZoneDistrictInline]


@admin.register(DeliveryMethod)
class DeliveryMethodAdmin(admin.ModelAdmin):
    list_display = ["name", "extra_charge", "is_active", "sort_order"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ["name", "division"]
    list_filter = ["division"]
    search_fields = ["name"]


@admin.register(ShippingChargeHistory)
class ShippingChargeHistoryAdmin(admin.ModelAdmin):
    list_display = ["zone_name", "old_charge", "new_charge", "changed_by", "created_at"]
    readonly_fields = [f.name for f in ShippingChargeHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
