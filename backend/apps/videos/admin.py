from django.contrib import admin

from .models import VideoCard


@admin.register(VideoCard)
class VideoCardAdmin(admin.ModelAdmin):
    list_display = ["title", "is_active", "sort_order"]
    list_filter = ["is_active"]
    search_fields = ["title"]
    filter_horizontal = ["products"]
