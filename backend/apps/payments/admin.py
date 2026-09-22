from django.contrib import admin

from .models import Payment, Refund


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    can_delete = False
    readonly_fields = [f.name for f in Refund._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Read-only: real changes go through the API so `Order.payment_status` stays in sync."""

    list_display = ["order", "method", "gateway", "status", "amount", "amount_received", "created_at"]
    list_filter = ["status", "method", "gateway"]
    search_fields = ["order__number", "transaction_id"]
    inlines = [RefundInline]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
