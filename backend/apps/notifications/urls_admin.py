"""Notification admin endpoints (Module 16), mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views_admin import NotificationLogViewSet, TemplateDetailView, TemplateListView

router = SimpleRouter()
router.register("notifications/logs", NotificationLogViewSet, basename="notification-log")

urlpatterns = [
    path("notifications/templates/", TemplateListView.as_view(), name="notification-templates"),
    path("notifications/templates/<str:event>/<str:channel>/", TemplateDetailView.as_view(), name="notification-template"),
    *router.urls,
]
