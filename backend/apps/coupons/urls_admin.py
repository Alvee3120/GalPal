"""Admin endpoints, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from .views_admin import AdminCouponUsageViewSet, AdminCouponViewSet

router = SimpleRouter()
router.register("coupons", AdminCouponViewSet, basename="admin-coupon")
router.register("coupon-usages", AdminCouponUsageViewSet, basename="admin-coupon-usage")

urlpatterns = router.urls
