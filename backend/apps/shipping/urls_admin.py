"""Admin endpoints, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AdminDeliveryMethodViewSet, AdminZoneViewSet

router = SimpleRouter()
router.register("shipping/zones", AdminZoneViewSet, basename="admin-shipping-zone")
router.register("shipping/methods", AdminDeliveryMethodViewSet, basename="admin-shipping-method")

urlpatterns = router.urls
