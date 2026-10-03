"""Admin/CCE endpoints, mounted at /api/v1/admin/orders/: the only admin area a CCE can reach."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from apps.cart.views_admin import OldCartDetailView, OldCartListView  # cart monitoring for Admin + CCE

from .views_admin import (
    AdminDashboardView, AdminOrderViewSet, DashboardView, HelperCustomerLookupView, HelperProductsView, HelperShippingView,
    InvoiceLayoutView,
)

router = SimpleRouter()
router.register("orders", AdminOrderViewSet, basename="admin-order")

urlpatterns = [
    # The helpers go first: the router's `orders/<pk>/` pattern accepts any non-slash string, "helpers" included.
    path("orders/helpers/products/", HelperProductsView.as_view(), name="admin-order-helper-products"),
    path("orders/helpers/shipping/", HelperShippingView.as_view(), name="admin-order-helper-shipping"),
    path("orders/helpers/customers/", HelperCustomerLookupView.as_view(), name="admin-order-helper-customers"),
    path("orders/dashboard/", DashboardView.as_view(), name="admin-order-dashboard"),
    path("orders/invoice-layout/", InvoiceLayoutView.as_view(), name="admin-invoice-layout-settings"),  # Admin + CCE (global)
    path("orders/old-carts/", OldCartListView.as_view(), name="admin-old-carts"),  # Admin + CCE: carts with items > 6h
    path("orders/old-carts/<int:pk>/", OldCartDetailView.as_view(), name="admin-old-cart-detail"),
    path("dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),  # Admin only (IsAdmin)
    *router.urls,
]
