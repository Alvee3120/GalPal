"""Admin/CCE endpoints, mounted at /api/v1/admin/orders/: the only admin area a CCE can reach."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views_admin import AdminOrderViewSet, HelperCustomerLookupView, HelperProductsView, HelperShippingView

router = SimpleRouter()
router.register("orders", AdminOrderViewSet, basename="admin-order")

urlpatterns = [
    # The helpers go first: the router's `orders/<pk>/` pattern accepts any non-slash string, "helpers" included.
    path("orders/helpers/products/", HelperProductsView.as_view(), name="admin-order-helper-products"),
    path("orders/helpers/shipping/", HelperShippingView.as_view(), name="admin-order-helper-shipping"),
    path("orders/helpers/customers/", HelperCustomerLookupView.as_view(), name="admin-order-helper-customers"),
    *router.urls,
]
