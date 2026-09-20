import factory

from apps.cart.models import Cart, CartItem
from apps.catalog.tests.factories import ProductFactory


class CartFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cart

    user = None
    token = factory.LazyFunction(Cart.new_token)


class CartItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CartItem

    cart = factory.SubFactory(CartFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = 1
