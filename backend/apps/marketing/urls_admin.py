"""Admin endpoints, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AdminTrackingEventViewSet

router = SimpleRouter()
router.register("tracking-events", AdminTrackingEventViewSet, basename="admin-tracking-event")

urlpatterns = router.urls
