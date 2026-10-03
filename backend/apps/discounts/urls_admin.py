"""Discount admin endpoints, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from .views_admin import DiscountViewSet

router = SimpleRouter()
router.register("discounts", DiscountViewSet, basename="discount")

urlpatterns = router.urls
