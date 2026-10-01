"""Storefront cart (guests and logged-in customers) and wishlist (logged-in only) endpoints, mounted at /api/v1/."""
from django.urls import path

from .views import CartItemDetailView, CartItemListView, CartView
from .views_wishlist import WishlistItemView, WishlistView

app_name = "cart"

urlpatterns = [
    path("cart/", CartView.as_view(), name="cart"),
    path("cart/items/", CartItemListView.as_view(), name="cart-item-list"),
    path("cart/items/<int:item_id>/", CartItemDetailView.as_view(), name="cart-item-detail"),
    path("wishlist/", WishlistView.as_view(), name="wishlist"),
    path("wishlist/<int:product_id>/", WishlistItemView.as_view(), name="wishlist-item"),
]
