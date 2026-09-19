from django.contrib import admin

from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Fallback only. Secrets are deliberately not editable here; use the admin API."""

    exclude = ("meta_capi_access_token", "ga4_api_secret")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
