"""Audit log admin endpoint (Module 18), mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AuditLogViewSet

router = SimpleRouter()
router.register("audit-logs", AuditLogViewSet, basename="audit-log")

urlpatterns = router.urls
