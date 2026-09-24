"""Storefront read-only endpoints, mounted at /api/v1/."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views
from .views_product import PublicProductViewSet
from .views_stock_notification import StockNotificationView

app_name = "catalog"

router = SimpleRouter()
router.register("categories", views.PublicCategoryViewSet, basename="category")
router.register("brands", views.PublicBrandViewSet, basename="brand")
router.register("tags", views.PublicTagViewSet, basename="tag")
router.register("products", PublicProductViewSet, basename="product")

urlpatterns = [
    path("stock-notifications/", StockNotificationView.as_view(), name="stock-notification"),
    *router.urls,
]
