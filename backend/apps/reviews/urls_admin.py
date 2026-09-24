"""Admin endpoints, mounted at /api/v1/admin/. Admin only; CCE may moderate (see views_admin)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AdminReviewViewSet

router = SimpleRouter()
router.register("reviews", AdminReviewViewSet, basename="admin-review")

urlpatterns = router.urls
