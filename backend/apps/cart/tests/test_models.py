import pytest
from django.db import IntegrityError, transaction

from apps.cart.models import Cart, CartItem
from apps.catalog.tests.factories import AttributeValueFactory, ProductFactory, ProductVariantFactory

from .factories import CartFactory, CartItemFactory

pytestmark = pytest.mark.django_db


def test_guest_cart_has_a_token_and_no_user():
    cart = CartFactory()
    assert cart.user is None and cart.token is not None
    assert str(cart) == f"Guest cart {cart.token}"


def test_user_cart_has_a_user_and_no_token(customer):
    cart = Cart.objects.create(user=customer)
    assert cart.token is None
    assert str(cart) == f"Cart for {customer}"


def test_database_rejects_both_user_and_token(customer):
    with pytest.raises(IntegrityError), transaction.atomic():
        Cart.objects.create(user=customer, token=Cart.new_token())


def test_database_rejects_neither_user_nor_token():
    with pytest.raises(IntegrityError), transaction.atomic():
        Cart.objects.create(user=None, token=None)


def test_one_cart_per_user():
    from apps.accounts.tests.factories import UserFactory

    user = UserFactory()
    Cart.objects.create(user=user)
    with pytest.raises(IntegrityError), transaction.atomic():
        Cart.objects.create(user=user)


def test_tokens_are_unique():
    token = Cart.new_token()
    Cart.objects.create(token=token)
    with pytest.raises(IntegrityError), transaction.atomic():
        Cart.objects.create(token=token)


def test_cart_item_str():
    product = ProductFactory()
    item = CartItemFactory(product=product, quantity=3)
    assert str(item) == f"3 x {product.pk}"


def test_no_variant_line_is_unique_per_product():
    cart = CartFactory()
    product = ProductFactory()
    CartItemFactory(cart=cart, product=product, variant=None)
    with pytest.raises(IntegrityError), transaction.atomic():
        CartItemFactory(cart=cart, product=product, variant=None)


def test_same_product_different_variant_is_fine():
    cart = CartFactory()
    product = ProductFactory(has_variants=True)
    v1 = ProductVariantFactory(product=product, attribute_values=[AttributeValueFactory()])
    v2 = ProductVariantFactory(product=product, attribute_values=[AttributeValueFactory()])
    CartItemFactory(cart=cart, product=product, variant=v1)
    CartItemFactory(cart=cart, product=product, variant=v2)
    assert cart.items.count() == 2


def test_same_variant_line_is_unique():
    cart = CartFactory()
    product = ProductFactory(has_variants=True)
    variant = ProductVariantFactory(product=product)
    CartItemFactory(cart=cart, product=product, variant=variant)
    with pytest.raises(IntegrityError), transaction.atomic():
        CartItemFactory(cart=cart, product=product, variant=variant)


def test_same_product_across_different_carts_is_fine():
    product = ProductFactory()
    CartItemFactory(product=product)
    CartItemFactory(product=product)  # different cart (default factory): no clash
    assert CartItem.objects.filter(product=product).count() == 2


def test_deleting_a_cart_deletes_its_items():
    cart = CartFactory()
    CartItemFactory(cart=cart)
    cart.delete()
    assert CartItem.objects.count() == 0


def test_deleting_a_user_deletes_their_cart(customer):
    Cart.objects.create(user=customer)
    user_pk = customer.pk
    customer.delete()  # a real hard delete for User (unlike Product/Category's soft delete)
    assert not Cart.objects.filter(user_id=user_pk).exists()
