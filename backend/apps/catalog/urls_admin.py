"""Admin endpoints, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from rest_framework.routers import SimpleRouter

from . import views_admin

router = SimpleRouter()  # SimpleRouter: no public API-root view listing admin URLs
router.register("categories", views_admin.AdminCategoryViewSet, basename="admin-category")
router.register("brands", views_admin.AdminBrandViewSet, basename="admin-brand")
router.register("tags", views_admin.AdminTagViewSet, basename="admin-tag")

urlpatterns = router.urls
