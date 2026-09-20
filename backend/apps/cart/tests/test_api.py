import pytest

from apps.cart.models import Cart
from apps.catalog.models import StockStatus
from apps.catalog.tests.factories import ProductFactory, ProductVariantFactory

pytestmark = pytest.mark.django_db

CART = "/api/v1/cart/"
ITEMS = "/api/v1/cart/items/"


def item_url(item_id):
    return f"{ITEMS}{item_id}/"


def with_token(client, token):
    client.credentials(HTTP_X_CART_TOKEN=str(token))
    return client


# --- guest: empty cart, add, token issuance ------------------------------------------------------


def test_empty_guest_cart_has_no_token_and_is_not_persisted(api_client):
    body = api_client.get(CART).json()
    assert body == {
        "cart_token": None, "items": [], "item_count": 0,
        "subtotal": "0.00", "discount": "0.00", "coupon": None,
        "shipping": {"amount": None, "note": "Calculated at checkout"},
        "total": "0.00",
    }
    assert Cart.objects.count() == 0


def test_adding_an_item_as_a_guest_issues_a_token(api_client):
    product = ProductFactory(stock_quantity=10)
    response = api_client.post(ITEMS, {"product_id": product.id, "quantity": 2}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["cart_token"] is not None
    assert response["X-Cart-Token"] == body["cart_token"]
    assert body["items"][0]["quantity"] == 2
    assert body["item_count"] == 2 and body["subtotal"] == "2000.00"  # 2 x regular_price (1000.00)


def test_resending_the_token_reaches_the_same_cart(api_client):
    product = ProductFactory(stock_quantity=10)
    token = api_client.post(ITEMS, {"product_id": product.id, "quantity": 1}, format="json").json()["cart_token"]
    body = with_token(api_client, token).get(CART).json()
    assert body["cart_token"] == token and body["item_count"] == 1


def test_unknown_or_garbage_token_behaves_like_no_token(api_client):
    import uuid

    for bad in ("not-a-uuid", str(uuid.uuid4())):
        body = with_token(api_client, bad).get(CART).json()
        assert body["cart_token"] is None and body["items"] == []


def test_stale_bearer_token_does_not_break_guest_cart_access(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage.garbage.garbage")
    assert api_client.get(CART).status_code == 200


# --- item shape --------------------------------------------------------------------------------


def test_item_shape_includes_product_and_computed_fields(api_client):
    product = ProductFactory(regular_price="500.00", discount_price="400.00", stock_quantity=10)
    body = api_client.post(ITEMS, {"product_id": product.id, "quantity": 2}, format="json").json()
    item = body["items"][0]
    assert item["product"]["id"] == product.id and item["product"]["slug"] == product.slug
    assert item["variant"] is None
    assert item["unit_price"] == "400.00" and item["line_total"] == "800.00"
    assert item["is_available"] is True and item["available_quantity"] == 10


def test_product_image_is_an_absolute_url(api_client):
    product = ProductFactory(stock_quantity=10)
    body = api_client.post(ITEMS, {"product_id": product.id, "quantity": 1}, format="json").json()
    image = body["items"][0]["product"]["feature_image"]
    assert image.startswith("http://testserver/media/products/")


def test_item_with_variant_shows_variant_shape(api_client):
    product = ProductFactory(has_variants=True, regular_price="500.00")
    variant = ProductVariantFactory(product=product, stock_quantity=5)
    body = api_client.post(ITEMS, {"product_id": product.id, "variant_id": variant.id, "quantity": 1}, format="json").json()
    variant_data = body["items"][0]["variant"]
    assert variant_data["id"] == variant.id and variant_data["sku"] == variant.sku


# --- add validation ------------------------------------------------------------------------------


def test_add_requires_a_variant_for_a_product_that_has_them(api_client):
    product = ProductFactory(has_variants=True)
    response = api_client.post(ITEMS, {"product_id": product.id, "quantity": 1}, format="json")
    assert response.status_code == 400 and "variant_id" in response.json()["error"]["details"]


def test_add_rejects_insufficient_stock(api_client):
    product = ProductFactory(manage_stock=True, stock_quantity=2)
    response = api_client.post(ITEMS, {"product_id": product.id, "quantity": 5}, format="json")
    assert response.status_code == 400 and "quantity" in response.json()["error"]["details"]


def test_add_unknown_product_is_400(api_client):
    response = api_client.post(ITEMS, {"product_id": 999999, "quantity": 1}, format="json")
    assert response.status_code == 400 and "product_id" in response.json()["error"]["details"]


def test_quantity_must_be_a_positive_integer_within_range(api_client):
    product = ProductFactory(stock_quantity=1000)
    for quantity in (0, -1, 1000):
        r = api_client.post(ITEMS, {"product_id": product.id, "quantity": quantity}, format="json")
        assert r.status_code == 400, quantity


# --- update / remove -------------------------------------------------------------------------------


def test_patch_sets_absolute_quantity(api_client):
    product = ProductFactory(stock_quantity=10)
    body = api_client.post(ITEMS, {"product_id": product.id, "quantity": 2}, format="json").json()
    token, item_id = body["cart_token"], body["items"][0]["id"]
    client = with_token(api_client, token)
    r = client.patch(item_url(item_id), {"quantity": 9}, format="json")
    assert r.status_code == 200 and r.json()["items"][0]["quantity"] == 9


def test_patch_rejects_zero_quantity(api_client):
    product = ProductFactory(stock_quantity=10)
    body = api_client.post(ITEMS, {"product_id": product.id, "quantity": 2}, format="json").json()
    client = with_token(api_client, body["cart_token"])
    r = client.patch(item_url(body["items"][0]["id"]), {"quantity": 0}, format="json")
    assert r.status_code == 400


def test_patch_beyond_stock_is_rejected(api_client):
    product = ProductFactory(manage_stock=True, stock_quantity=5)
    body = api_client.post(ITEMS, {"product_id": product.id, "quantity": 2}, format="json").json()
    client = with_token(api_client, body["cart_token"])
    r = client.patch(item_url(body["items"][0]["id"]), {"quantity": 6}, format="json")
    assert r.status_code == 400
    assert client.get(CART).json()["items"][0]["quantity"] == 2  # unchanged


def test_delete_removes_the_item(api_client):
    product = ProductFactory(stock_quantity=10)
    body = api_client.post(ITEMS, {"product_id": product.id, "quantity": 1}, format="json").json()
    client = with_token(api_client, body["cart_token"])
    r = client.delete(item_url(body["items"][0]["id"]))
    assert r.status_code == 200 and r.json()["items"] == []


def test_item_operations_are_scoped_to_the_owning_cart(api_client):
    product = ProductFactory(stock_quantity=10)
    mine = api_client.post(ITEMS, {"product_id": product.id, "quantity": 1}, format="json").json()
    other_client = with_token(type(api_client)(), None)  # a fresh guest, no token yet
    assert other_client.patch(item_url(mine["items"][0]["id"]), {"quantity": 2}, format="json").status_code == 404
    assert other_client.delete(item_url(mine["items"][0]["id"])).status_code == 404


def test_item_not_found_for_a_bad_id(api_client):
    product = ProductFactory(stock_quantity=10)
    body = api_client.post(ITEMS, {"product_id": product.id, "quantity": 1}, format="json").json()
    client = with_token(api_client, body["cart_token"])
    assert client.patch(item_url(999999), {"quantity": 1}, format="json").status_code == 404
    assert client.delete(item_url(999999)).status_code == 404


# --- logged-in customer ---------------------------------------------------------------------------


def test_logged_in_customer_cart_needs_no_token(auth_client, customer):
    product = ProductFactory(stock_quantity=10)
    client = auth_client(customer)
    body = client.post(ITEMS, {"product_id": product.id, "quantity": 2}, format="json").json()
    assert body["cart_token"] is None
    assert client.get(CART).json()["item_count"] == 2


def test_customer_cart_is_scoped_to_that_customer(auth_client):
    from apps.accounts.tests.factories import UserFactory

    a, b = UserFactory(), UserFactory()
    product = ProductFactory(stock_quantity=10)
    auth_client(a).post(ITEMS, {"product_id": product.id, "quantity": 3}, format="json")
    assert auth_client(b).get(CART).json()["item_count"] == 0


def test_a_cart_token_is_ignored_for_a_logged_in_customer(auth_client, customer):
    from .factories import CartItemFactory, CartFactory

    guest = CartFactory()
    CartItemFactory(cart=guest, product=ProductFactory(stock_quantity=10))
    client = auth_client(customer)
    client.credentials(HTTP_AUTHORIZATION=client._credentials.get("HTTP_AUTHORIZATION"), HTTP_X_CART_TOKEN=str(guest.token))
    assert client.get(CART).json()["item_count"] == 0  # the guest cart, not the customer's


# --- merge on login --------------------------------------------------------------------------------


def test_login_merges_the_guest_cart(api_client, customer, password):
    product = ProductFactory(stock_quantity=10)
    add = api_client.post(ITEMS, {"product_id": product.id, "quantity": 2}, format="json").json()
    login_client = with_token(type(api_client)(), add["cart_token"])
    r = login_client.post("/api/v1/auth/login/", {"identifier": customer.phone, "password": password}, format="json")
    assert r.status_code == 200
    access = r.json()["access"]
    cart_client = type(api_client)()
    cart_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    body = cart_client.get(CART).json()
    assert body["item_count"] == 2
    assert not Cart.objects.filter(token=add["cart_token"]).exists()


def test_register_also_merges_the_guest_cart(api_client):
    product = ProductFactory(stock_quantity=10)
    add = api_client.post(ITEMS, {"product_id": product.id, "quantity": 1}, format="json").json()
    register_client = with_token(type(api_client)(), add["cart_token"])
    r = register_client.post(
        "/api/v1/auth/register/",
        {"full_name": "New Shopper", "phone": "01799999999", "password": "Str0ng!Passw0rd"},
        format="json",
    )
    assert r.status_code == 201
    access = r.json()["access"]
    cart_client = type(api_client)()
    cart_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    assert cart_client.get(CART).json()["item_count"] == 1


def test_login_without_a_cart_token_does_not_error(api_client, customer, password):
    r = api_client.post("/api/v1/auth/login/", {"identifier": customer.phone, "password": password}, format="json")
    assert r.status_code == 200
