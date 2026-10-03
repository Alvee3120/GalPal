from django.contrib import admin

from .models import NotificationLog, NotificationTemplate


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ["event", "channel", "is_active", "updated_at"]
    list_filter = ["channel", "is_active"]


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ["event", "channel", "recipient", "status", "attempts", "created_at"]
    list_filter = ["event", "channel", "status"]
    search_fields = ["recipient"]
    raw_id_fields = ["order", "user"]
