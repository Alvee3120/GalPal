from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor_name", "actor_role", "action", "target_label", "ip_address", "status_code"]
    list_filter = ["actor_role", "action"]
    search_fields = ["actor_name", "target_label", "path"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False
