"""Admin endpoints, mounted at /api/v1/admin/. Admin only (CCE gets 403)."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views_admin
from . import views_product_admin as pv
from .views_stock_notification import StaffStockNotificationViewSet

router = SimpleRouter()  # SimpleRouter: no public API-root view listing admin URLs
router.register("categories", views_admin.AdminCategoryViewSet, basename="admin-category")
router.register("brands", views_admin.AdminBrandViewSet, basename="admin-brand")
router.register("tags", views_admin.AdminTagViewSet, basename="admin-tag")
router.register("products", pv.AdminProductViewSet, basename="admin-product")
router.register("product-attributes", pv.AdminProductAttributeViewSet, basename="admin-product-attribute")
router.register("attribute-values", pv.AdminAttributeValueViewSet, basename="admin-attribute-value")
router.register("stock-movements", pv.AdminStockMovementViewSet, basename="admin-stock-movement")
router.register("stock-notifications", StaffStockNotificationViewSet, basename="admin-stock-notification")

_images = pv.AdminProductImageViewSet
_variants = pv.AdminVariantViewSet

urlpatterns = [
    # Must come before *router.urls: "picker" would otherwise match the router's own
    # products/<pk>/ detail route (its lookup regex accepts any non-slash string, not just ints).
    path("products/picker/", pv.ProductPickerView.as_view(), name="admin-product-picker"),
    *router.urls,
    path("stock/adjust/", pv.StockAdjustmentView.as_view(), name="admin-stock-adjust"),
    path("products/<int:product_pk>/images/", _images.as_view({"get": "list", "post": "create"}), name="admin-product-image-list"),
    path("products/<int:product_pk>/images/reorder/", _images.as_view({"post": "reorder"}), name="admin-product-image-reorder"),
    path(
        "products/<int:product_pk>/images/<int:pk>/",
        _images.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="admin-product-image-detail",
    ),
    path("products/<int:product_pk>/variants/", _variants.as_view({"get": "list", "post": "create"}), name="admin-product-variant-list"),
    path(
        "products/<int:product_pk>/variants/<int:pk>/",
        _variants.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="admin-product-variant-detail",
    ),
]
