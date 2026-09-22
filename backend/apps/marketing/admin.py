from django.contrib import admin

from .models import TrackingEventLog


@admin.register(TrackingEventLog)
class TrackingEventLogAdmin(admin.ModelAdmin):
    list_display = ["event_name", "destination", "success", "order", "attempt", "created_at"]
    list_filter = ["event_name", "destination", "success"]
    search_fields = ["event_id", "order__number"]
    readonly_fields = [f.name for f in TrackingEventLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
