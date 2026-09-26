"""Admin endpoint, mounted at /api/v1/admin/. Admin and CCE manage video cards (see views_admin.cce_actions)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AdminVideoCardViewSet

router = SimpleRouter()
router.register("videos", AdminVideoCardViewSet, basename="admin-video")

urlpatterns = router.urls
