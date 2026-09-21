"""Storefront endpoints, mounted at /api/v1/."""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CheckoutView, MyOrderViewSet, TrackOrderView

app_name = "orders"

router = SimpleRouter()
router.register("orders", MyOrderViewSet, basename="my-order")

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    # Before the router: its `orders/<number>/` pattern would otherwise take "track" for an order number.
    path("orders/track/", TrackOrderView.as_view(), name="track"),
    *router.urls,
]
