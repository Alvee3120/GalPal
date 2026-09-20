"""Admin endpoints, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views_admin import AdminHeroBannerViewSet, AdminSliderConfigView

router = SimpleRouter()
router.register("hero-banners", AdminHeroBannerViewSet, basename="admin-hero-banner")

urlpatterns = [
    path("hero-slider-config/", AdminSliderConfigView.as_view(), name="admin-hero-slider-config"),
    *router.urls,
]
