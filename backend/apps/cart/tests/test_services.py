from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.core.exceptions import ValidationError

from apps.cart import services
from apps.cart.models import Cart, CartItem
from apps.catalog.models import StockStatus
from apps.catalog.tests.factories import AttributeValueFactory, ProductFactory, ProductVariantFactory

from .factories import CartFactory, CartItemFactory

pytestmark = pytest.mark.django_db


def code_of(exc, field):
    return exc.value.error_dict[field][0].code


def fake_request(user=None, token=None):
    request = MagicMock()
    request.user = user
    request.headers = {services.CART_TOKEN_HEADER: str(token)} if token else {}
    return request


# --- get_cart --------------------------------------------------------------------------------


def test_get_cart_for_a_logged_in_user_creates_one_if_missing(customer):
    cart = services.get_cart(fake_request(user=customer))
    assert cart.user == customer
    assert services.get_cart(fake_request(user=customer)).pk == cart.pk  # idempotent


def test_get_cart_ignores_the_token_header_for_a_logged_in_user(customer):
    guest_cart = CartFactory()
    cart = services.get_cart(fake_request(user=customer, token=guest_cart.token))
    assert cart.user == customer and cart.pk != guest_cart.pk


def test_get_cart_for_a_guest_with_a_valid_token():
    guest_cart = CartFactory()
    assert services.get_cart(fake_request(token=guest_cart.token)).pk == guest_cart.pk


def test_get_cart_returns_none_for_a_guest_with_no_or_bad_token():
    assert services.get_cart(fake_request()) is None
    assert services.get_cart(fake_request(token="not-a-uuid")) is None
    import uuid

    assert services.get_cart(fake_request(token=uuid.uuid4())) is None  # well-formed but unknown


def test_get_cart_create_true_makes_a_fresh_guest_cart_when_none_found():
    cart = services.get_cart(fake_request(), create=True)
    assert cart.token is not None and cart.user is None
    assert Cart.objects.filter(pk=cart.pk).exists()


# --- add_item ----------------------------------------------------------------------------------


def test_add_item_creates_a_new_line():
    cart = CartFactory()
    product = ProductFactory(stock_quantity=10)
    item = services.add_item(cart, product_id=product.pk, quantity=2)
    assert item.quantity == 2 and item.variant is None


def test_add_item_increments_an_existing_line():
    cart = CartFactory()
    product = ProductFactory(stock_quantity=10)
    services.add_item(cart, product_id=product.pk, quantity=2)
    item = services.add_item(cart, product_id=product.pk, quantity=3)
    assert item.quantity == 5 and CartItem.objects.filter(cart=cart, product=product).count() == 1


def test_add_item_rejects_a_draft_product():
    cart = CartFactory()
    product = ProductFactory(status="draft")
    with pytest.raises(ValidationError) as exc:
        services.add_item(cart, product_id=product.pk, quantity=1)
    assert code_of(exc, "product_id") == "product_unavailable"


def test_add_item_rejects_unknown_product():
    with pytest.raises(ValidationError) as exc:
        services.add_item(CartFactory(), product_id=999999, quantity=1)
    assert code_of(exc, "product_id") == "not_found"


def test_add_item_requires_a_variant_when_the_product_has_them():
    product = ProductFactory(has_variants=True)
    with pytest.raises(ValidationError) as exc:
        services.add_item(CartFactory(), product_id=product.pk, quantity=1)
    assert code_of(exc, "variant_id") == "variant_required"


def test_add_item_rejects_a_variant_on_a_product_without_variants():
    product = ProductFactory(has_variants=False)
    variant = ProductVariantFactory(product=ProductFactory(has_variants=True))
    with pytest.raises(ValidationError) as exc:
        services.add_item(CartFactory(), product_id=product.pk, variant_id=variant.pk, quantity=1)
    assert code_of(exc, "variant_id") == "variant_not_allowed"


def test_add_item_rejects_a_variant_from_a_different_product():
    a = ProductFactory(has_variants=True)
    b = ProductFactory(has_variants=True)
    variant_of_b = ProductVariantFactory(product=b)
    with pytest.raises(ValidationError) as exc:
        services.add_item(CartFactory(), product_id=a.pk, variant_id=variant_of_b.pk, quantity=1)
    assert code_of(exc, "variant_id") == "variant_mismatch"


def test_add_item_rejects_an_inactive_variant():
    product = ProductFactory(has_variants=True)
    variant = ProductVariantFactory(product=product, is_active=False)
    with pytest.raises(ValidationError) as exc:
        services.add_item(CartFactory(), product_id=product.pk, variant_id=variant.pk, quantity=1)
    assert code_of(exc, "variant_id") == "variant_unavailable"


def test_add_item_with_a_valid_variant():
    product = ProductFactory(has_variants=True)
    variant = ProductVariantFactory(product=product, stock_quantity=5)
    item = services.add_item(CartFactory(), product_id=product.pk, variant_id=variant.pk, quantity=2)
    assert item.variant == variant


def test_add_item_rejects_insufficient_stock():
    product = ProductFactory(manage_stock=True, stock_quantity=3)
    with pytest.raises(ValidationError) as exc:
        services.add_item(CartFactory(), product_id=product.pk, quantity=5)
    assert code_of(exc, "quantity") == "insufficient_stock"
    assert not CartItem.objects.filter(product=product).exists()  # nothing partially added


def test_add_item_stock_check_accounts_for_existing_quantity():
    cart = CartFactory()
    product = ProductFactory(manage_stock=True, stock_quantity=5)
    services.add_item(cart, product_id=product.pk, quantity=4)
    with pytest.raises(ValidationError):
        services.add_item(cart, product_id=product.pk, quantity=2)  # 4+2=6 > 5
    assert CartItem.objects.get(cart=cart, product=product).quantity == 4  # unchanged


def test_add_item_unmanaged_stock_is_uncapped():
    product = ProductFactory(manage_stock=False, stock_quantity=0)
    item = services.add_item(CartFactory(), product_id=product.pk, quantity=500)
    assert item.quantity == 500


def test_add_item_backorder_is_uncapped():
    product = ProductFactory(manage_stock=True, stock_quantity=0, stock_status=StockStatus.BACKORDER)
    item = services.add_item(CartFactory(), product_id=product.pk, quantity=100)
    assert item.quantity == 100


# --- set_item_quantity -------------------------------------------------------------------------


def test_set_item_quantity_updates_the_line():
    item = CartItemFactory(product=ProductFactory(stock_quantity=10), quantity=1)
    services.set_item_quantity(item, 7)
    item.refresh_from_db()
    assert item.quantity == 7


def test_set_item_quantity_respects_stock():
    item = CartItemFactory(product=ProductFactory(manage_stock=True, stock_quantity=5), quantity=1)
    with pytest.raises(ValidationError):
        services.set_item_quantity(item, 6)
    item.refresh_from_db()
    assert item.quantity == 1


def test_set_item_quantity_for_a_variant_checks_the_variant_stock():
    product = ProductFactory(has_variants=True, stock_quantity=999)
    variant = ProductVariantFactory(product=product, manage_stock=True, stock_quantity=2)
    item = CartItemFactory(product=product, variant=variant, quantity=1)
    with pytest.raises(ValidationError):
        services.set_item_quantity(item, 3)


# --- remove_item ---------------------------------------------------------------------------------


def test_remove_item():
    item = CartItemFactory()
    services.remove_item(item)
    assert not CartItem.objects.filter(pk=item.pk).exists()


# --- merge_guest_cart_into_user -----------------------------------------------------------------


def test_merge_moves_items_into_a_new_user_cart(customer):
    guest = CartFactory()
    product = ProductFactory(stock_quantity=10)
    CartItemFactory(cart=guest, product=product, quantity=2)
    services.merge_guest_cart_into_user(guest.token, customer)
    user_cart = Cart.objects.get(user=customer)
    assert user_cart.items.get(product=product).quantity == 2
    assert not Cart.objects.filter(pk=guest.pk).exists()


def test_merge_combines_quantities_for_a_line_in_both_carts(customer):
    product = ProductFactory(stock_quantity=100)
    user_cart = Cart.objects.create(user=customer)
    CartItemFactory(cart=user_cart, product=product, quantity=3)
    guest = CartFactory()
    CartItemFactory(cart=guest, product=product, quantity=4)
    services.merge_guest_cart_into_user(guest.token, customer)
    assert CartItem.objects.get(cart=user_cart, product=product).quantity == 7


def test_merge_caps_combined_quantity_at_available_stock(customer):
    product = ProductFactory(manage_stock=True, stock_quantity=5)
    user_cart = Cart.objects.create(user=customer)
    CartItemFactory(cart=user_cart, product=product, quantity=3)
    guest = CartFactory()
    CartItemFactory(cart=guest, product=product, quantity=4)  # 3+4=7 > 5 in stock
    services.merge_guest_cart_into_user(guest.token, customer)
    assert CartItem.objects.get(cart=user_cart, product=product).quantity == 5


def test_merge_drops_a_line_that_no_longer_fits_at_all(customer):
    product = ProductFactory(manage_stock=True, stock_quantity=0, stock_status="out_of_stock")
    guest = CartFactory()
    CartItemFactory(cart=guest, product=product, quantity=1)
    services.merge_guest_cart_into_user(guest.token, customer)
    user_cart = Cart.objects.get(user=customer)
    assert not user_cart.items.filter(product=product).exists()


def test_merge_with_no_token_or_unknown_token_is_a_silent_no_op(customer):
    import uuid

    assert services.merge_guest_cart_into_user(None, customer) is None
    assert services.merge_guest_cart_into_user(uuid.uuid4(), customer) is None
    assert not Cart.objects.filter(user=customer).exists()


def test_merge_never_raises_even_if_something_goes_wrong(customer, monkeypatch):
    guest = CartFactory()
    CartItemFactory(cart=guest, product=ProductFactory())
    monkeypatch.setattr(services, "available_quantity", MagicMock(side_effect=RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        # The service itself doesn't swallow errors (that's the call site's job, in
        # apps.accounts.views._merge_guest_cart); this just documents that boundary.
        services.merge_guest_cart_into_user(guest.token, customer)


# --- summarize ------------------------------------------------------------------------------------


def test_summarize_empty_cart_or_none():
    for cart in (None, CartFactory()):
        summary = services.summarize(cart)
        assert summary["rows"] == [] and summary["subtotal"] == Decimal("0.00")
        assert summary["item_count"] == 0 and summary["total"] == Decimal("0.00")
        assert summary["discount"] == Decimal("0.00")
        assert summary["shipping"] == {"amount": None, "note": "Calculated at checkout"}


def test_summarize_computes_totals_live():
    cart = CartFactory()
    a = CartItemFactory(cart=cart, product=ProductFactory(regular_price="100.00", stock_quantity=10), quantity=2)
    b = CartItemFactory(cart=cart, product=ProductFactory(regular_price="50.00", discount_price="40.00", stock_quantity=10), quantity=1)
    summary = services.summarize(cart)
    assert summary["subtotal"] == Decimal("240.00")  # 2*100 + 1*40
    assert summary["total"] == Decimal("240.00")
    assert summary["item_count"] == 3


def test_summarize_reflects_a_live_price_change_not_a_snapshot():
    cart = CartFactory()
    product = ProductFactory(regular_price="100.00", stock_quantity=10)
    CartItemFactory(cart=cart, product=product, quantity=1)
    assert services.summarize(cart)["subtotal"] == Decimal("100.00")
    product.regular_price = "150.00"
    product.save()
    assert services.summarize(cart)["subtotal"] == Decimal("150.00")


def test_summarize_excludes_unavailable_lines_from_totals_but_still_lists_them():
    cart = CartFactory()
    available = CartItemFactory(cart=cart, product=ProductFactory(regular_price="100.00", stock_quantity=10), quantity=1)
    gone = CartItemFactory(cart=cart, product=ProductFactory(regular_price="100.00", status="draft"), quantity=1)
    summary = services.summarize(cart)
    assert summary["subtotal"] == Decimal("100.00")
    by_availability = {row["item"].pk: row["is_available"] for row in summary["rows"]}
    assert by_availability == {available.pk: True, gone.pk: False}


def test_summarize_marks_a_line_unavailable_when_quantity_exceeds_current_stock():
    cart = CartFactory()
    product = ProductFactory(manage_stock=True, stock_quantity=2, regular_price="10.00")
    item = CartItemFactory(cart=cart, product=product, quantity=5)  # stock dropped after it was added
    summary = services.summarize(cart)
    row = summary["rows"][0]
    assert row["is_available"] is False and row["available_quantity"] == 2
    assert item.pk == row["item"].pk and summary["subtotal"] == Decimal("0.00")
