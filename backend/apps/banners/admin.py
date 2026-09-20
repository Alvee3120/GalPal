from django.contrib import admin

from .models import HeroBanner, HeroSliderConfig


@admin.register(HeroSliderConfig)
class HeroSliderConfigAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not HeroSliderConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HeroBanner)
class HeroBannerAdmin(admin.ModelAdmin):
    list_display = ["title", "is_active", "sort_order", "start_at", "end_at"]
    list_filter = ["is_active"]
    search_fields = ["title"]
