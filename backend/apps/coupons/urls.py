"""Public endpoint, mounted at /api/v1/. POST applies a coupon to the current cart, DELETE removes it."""
from django.urls import path

from .views import CartCouponView

app_name = "coupons"

urlpatterns = [path("cart/coupon/", CartCouponView.as_view(), name="cart-coupon")]
