from django.contrib import admin

from .models import Order, OrderItem, OrderNote, OrderStatusHistory


class _ReadOnlyInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class OrderItemInline(_ReadOnlyInline):
    model = OrderItem
    readonly_fields = [f.name for f in OrderItem._meta.fields]


class OrderHistoryInline(_ReadOnlyInline):
    model = OrderStatusHistory
    readonly_fields = [f.name for f in OrderStatusHistory._meta.fields]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """A read-only look at orders. Real changes go through the API so stock, coupons and history stay consistent."""

    list_display = ["number", "status", "source", "customer_name", "phone", "grand_total", "created_at"]
    list_filter = ["status", "source", "is_manual"]
    search_fields = ["number", "phone", "customer_name"]
    inlines = [OrderItemInline, OrderHistoryInline]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Order._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(OrderNote)
class OrderNoteAdmin(admin.ModelAdmin):
    list_display = ["order", "author", "created_at"]
