"""Admin endpoint, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AdminVideoCardViewSet

router = SimpleRouter()
router.register("videos", AdminVideoCardViewSet, basename="admin-video")

urlpatterns = router.urls
