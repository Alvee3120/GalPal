"""Storefront read-only endpoints, mounted at /api/v1/."""
from rest_framework.routers import SimpleRouter

from . import views

app_name = "catalog"

router = SimpleRouter()
router.register("categories", views.PublicCategoryViewSet, basename="category")
router.register("brands", views.PublicBrandViewSet, basename="brand")
router.register("tags", views.PublicTagViewSet, basename="tag")

urlpatterns = router.urls
