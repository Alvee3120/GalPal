"""Admin endpoints, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AdminPaymentViewSet

router = SimpleRouter()
router.register("payments", AdminPaymentViewSet, basename="admin-payment")

urlpatterns = router.urls
