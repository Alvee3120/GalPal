"""Storefront cart endpoints, mounted at /api/v1/. Open to guests and logged-in customers."""
from django.urls import path

from .views import CartItemDetailView, CartItemListView, CartView

app_name = "cart"

urlpatterns = [
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/items/", CartItemListView.as_view(), name="cart-item-list"),
    path("cart/items/<int:item_id>/", CartItemDetailView.as_view(), name="cart-item-detail"),
]
