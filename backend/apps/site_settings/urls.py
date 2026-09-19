"""Public endpoint, mounted at /api/v1/."""
from django.urls import path

from .views import PublicSiteSettingsView

app_name = "site_settings"

urlpatterns = [
    path("site-settings/", PublicSiteSettingsView.as_view(), name="public"),
]
