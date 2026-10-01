"""Wishlist business logic (Module 7): a logged-in customer's saved products. Only published products can be added."""

from apps.catalog.filters_product import annotate_effective_price
from apps.catalog.models import Product, ProductStatus

from .exceptions import field_error
from .models import WishlistItem


def add(user, product_id):
    """Save a published product to the user's wishlist (idempotent). Returns (item, created)."""
    product = Product.objects.filter(pk=product_id, status=ProductStatus.PUBLISHED).first()
    if product is None:
        raise field_error("product_id", "Product not found.", "not_found")
    return WishlistItem.objects.get_or_create(user=user, product=product)


def remove(user, product_id):
    """Remove a product from the user's wishlist. Returns whether anything was removed."""
    deleted, _ = WishlistItem.objects.filter(user=user, product_id=product_id).delete()
    return bool(deleted)


def products(user):
    """The user's saved products that are still published, newest first, ready for the product card serializer."""
    ids = list(WishlistItem.objects.filter(user=user).values_list("product_id", flat=True))
    queryset = Product.objects.filter(pk__in=ids, status=ProductStatus.PUBLISHED).select_related("brand").prefetch_related(
        "category_links__category"
    )
    by_id = {p.pk: p for p in annotate_effective_price(queryset)}
    return [by_id[i] for i in ids if i in by_id]
