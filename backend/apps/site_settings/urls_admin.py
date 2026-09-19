"""Admin endpoint, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from django.urls import path

from .views import AdminSiteSettingsView

urlpatterns = [
    path("site-settings/", AdminSiteSettingsView.as_view(), name="admin-site-settings"),
]
