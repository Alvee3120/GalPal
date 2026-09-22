"""Admin endpoints, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AdminReviewViewSet

router = SimpleRouter()
router.register("reviews", AdminReviewViewSet, basename="admin-review")

urlpatterns = router.urls
