"""Storefront endpoints, mounted at /api/v1/."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CheckoutView, MyOrderInvoiceView, MyOrderViewSet, TrackedOrderInvoiceView, TrackOrderView

app_name = "orders"

router = SimpleRouter()
router.register("orders", MyOrderViewSet, basename="my-order")

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    # Before the router: its `orders/<number>/` pattern would otherwise take "track" for an order number.
    path("orders/track/", TrackOrderView.as_view(), name="track"),
    path("orders/track/invoice/", TrackedOrderInvoiceView.as_view(), name="track-invoice"),
    path("orders/track/invoice/pdf/", TrackedOrderInvoiceView.as_view(pdf=True), name="track-invoice-pdf"),
    path("orders/<str:number>/invoice/", MyOrderInvoiceView.as_view(), name="my-order-invoice"),
    path("orders/<str:number>/invoice/pdf/", MyOrderInvoiceView.as_view(pdf=True), name="my-order-invoice-pdf"),
    *router.urls,
]
