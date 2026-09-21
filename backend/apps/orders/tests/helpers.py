"""Shared builders for the orders tests."""
from apps.catalog.tests.factories import ProductFactory

CHECKOUT = "/api/v1/checkout/"
CART_ITEMS = "/api/v1/cart/items/"
CART_COUPON = "/api/v1/cart/coupon/"


def payload(**overrides):
    base = {
        "name": "Rina Akter", "phone": "01712345678", "email": "", "district": "Dhaka", "area": "Mirpur",
        "address_line": "House 4, Road 2", "payment_method": "cod",
    }
    base.update(overrides)
    return base


def add_to_cart(client, product, quantity=1, variant=None):
    """Put `product` in a (guest or logged-in) client's cart; a guest's token is remembered on the client."""
    body = {"product_id": product.id, "quantity": quantity}
    if variant is not None:
        body["variant_id"] = variant.id
    response = client.post(CART_ITEMS, body, format="json")
    assert response.status_code in (200, 201), response.json()
    token = response.json().get("cart_token")
    if token:
        client.credentials(HTTP_X_CART_TOKEN=token)
    return response


def place(client, product=None, quantity=1, **overrides):
    """Guest/customer checkout with one product; returns the response."""
    if product is not None:
        add_to_cart(client, product, quantity)
    return client.post(CHECKOUT, payload(**overrides), format="json")


def details(response):
    return response.json()["error"]["details"]


def code(response):
    return response.json()["error"]["code"]


def new_order(staff=None, product=None, quantity=1, **overrides):
    """An order made through the real service (as a staff-entered order), for tests that need one to exist."""
    from apps.orders import services

    product = product or ProductFactory(stock_quantity=20, manage_stock=True, regular_price="500.00")
    data = {
        "name": "Rina Akter", "phone": "01712345678", "district": "Dhaka", "address_line": "House 4", "payment_method": "cod",
        "source": "call", "items": [{"product_id": product.id, "quantity": quantity}],
    }
    data.update(overrides)
    return services.create_manual_order(staff=staff, data=data).order
