import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.catalog.models import Product, ProductVariant
from apps.core.models import TimeStampedModel
from apps.coupons.models import Coupon

_quantity_range = [MinValueValidator(1), MaxValueValidator(999)]


class Cart(TimeStampedModel):
    """
    A shopping cart, owned either by a logged-in user or by a guest.

    A logged-in user's cart has `user` set and `token` empty. A guest's cart has `token` set (a
    random value the client stores and resends via the `X-Cart-Token` header) and `user` empty.
    Never both, never neither — see `services.get_cart`, the only place a `Cart` should be
    looked up or created. `services.merge_guest_cart_into_user` folds a guest cart into the
    user's own cart on login and deletes it.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="cart"
    )
    token = models.UUIDField(null=True, blank=True, unique=True, default=None)
    coupon = models.ForeignKey(
        Coupon, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Applied via apps.coupons.services.apply_coupon_to_cart; discount is computed live, never stored.",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(user__isnull=False) & models.Q(token__isnull=True))
                    | (models.Q(user__isnull=True) & models.Q(token__isnull=False))
                ),
                name="cart_exactly_one_owner",
            ),
        ]

    def __str__(self):
        return f"Cart for {self.user}" if self.user_id else f"Guest cart {self.token}"

    @staticmethod
    def new_token():
        return uuid.uuid4()


class CartItem(TimeStampedModel):
    """
    One line of a cart: a product (and, if it has variants, one of them) plus a quantity.

    No price is stored here — `services`/the serializer always compute it fresh from the
    product/variant's current price, so a cart never shows a stale price. Stock and active-status
    are similarly checked live, not at add-time, since either can change while the item sits in
    the cart (see `CartItem.is_available` usage in `services.summarize`).
    """

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="+")
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField(default=1, validators=_quantity_range)

    class Meta:
        ordering = ["id"]
        constraints = [
            # Two plain constraints, not one on (cart, product, variant): Postgres treats every
            # NULL as distinct, so a single constraint would let a non-variant product (variant is
            # NULL) be added as two separate rows instead of colliding.
            models.UniqueConstraint(
                fields=["cart", "product", "variant"], name="cart_item_unique_line_with_variant"
            ),
            models.UniqueConstraint(
                fields=["cart", "product"], condition=models.Q(variant__isnull=True), name="cart_item_unique_line_no_variant"
            ),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product_id}" + (f" ({self.variant_id})" if self.variant_id else "")
