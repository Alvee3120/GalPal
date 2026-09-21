from decimal import Decimal

import pytest

from apps.cart.models import Cart
from apps.catalog.models import ProductVariant, StockMovement
from apps.catalog.tests.factories import ProductFactory
from apps.coupons.models import CouponUsage
from apps.coupons.tests.factories import CouponFactory
from apps.orders.models import Order

from .conftest import set_site
from .helpers import CART_COUPON, CHECKOUT, add_to_cart, code, details, payload, place

pytestmark = pytest.mark.django_db

D = Decimal


# --- the happy path and its snapshot -----------------------------------------------------------------------------


def test_a_guest_order_is_created_with_server_computed_totals(api_client, product):
    r = place(api_client, product, quantity=2)
    assert r.status_code == 201
    body = r.json()
    order = Order.objects.get()
    assert body["account_created"] is False
    assert body["order"]["number"] == order.number and order.number.startswith("GP-")
    assert (order.status, order.source, order.is_manual, order.created_by, order.customer) == ("pending", "website", False, None, None)
    assert (order.subtotal, order.discount_amount, order.shipping_charge, order.tax_amount, order.grand_total) == (
        D("1000.00"), D("0.00"), D("70.00"), D("0.00"), D("1070.00"))
    assert (order.shipping_zone_name, order.customer_name, order.phone, order.district) == ("Inside Dhaka", "Rina Akter", "01712345678", "Dhaka")
    assert order.shipping_zone is not None and order.payment_method == "cod" and order.payment_status == "unpaid"


def test_items_are_a_snapshot_of_the_product_at_order_time(api_client, product):
    original_name, original_sku = product.name, product.sku
    place(api_client, product, quantity=3)
    item = Order.objects.get().items.get()
    assert (item.product_name, item.sku, item.quantity) == (original_name, original_sku, 3)
    assert (item.unit_price, item.regular_price, item.line_total) == (D("500.00"), D("500.00"), D("1500.00"))
    assert item.image == product.feature_image.name
    product.name, product.regular_price = "Renamed", D("999.00")
    product.save()
    item.refresh_from_db()
    assert item.product_name == original_name and item.unit_price == D("500.00")  # later catalog edits can't rewrite the order


def test_the_sale_price_is_what_gets_charged(api_client):
    product = ProductFactory(regular_price="500.00", discount_price="400.00", stock_quantity=5)
    place(api_client, product)
    item = Order.objects.get().items.get()
    assert (item.unit_price, item.regular_price) == (D("400.00"), D("500.00"))


def test_the_response_has_no_internal_fields(api_client, product):
    order = place(api_client, product).json()["order"]
    for leaked in ("source", "source_note", "created_by", "notes", "ip_address", "fingerprint", "is_manual", "id"):
        assert leaked not in order
    assert set(order["history"][0]) == {"status", "created_at"}  # no staff names or internal notes


def test_the_cart_is_emptied_after_a_successful_checkout(api_client, product):
    place(api_client, product)
    cart = Cart.objects.get()
    assert cart.items.count() == 0 and cart.coupon is None


def test_each_order_gets_a_distinct_readable_number(api_client):
    numbers = set()
    for i in range(3):
        p = ProductFactory(stock_quantity=5)
        numbers.add(place(api_client, p, phone=f"0171234567{i}").json()["order"]["number"])
    assert len(numbers) == 3 and all(len(n) == len("GP-260921-7K3F") for n in numbers)


def test_tax_from_site_settings_is_applied_to_the_discounted_subtotal(api_client, product):
    set_site(tax_percent=D("5.00"))
    place(api_client, product, quantity=2)
    order = Order.objects.get()
    assert (order.tax_percent, order.tax_amount, order.grand_total) == (D("5.00"), D("50.00"), D("1120.00"))  # 1000 + 70 + 50


def test_a_logged_in_customer_order_is_linked_and_needs_no_email(auth_client, customer, product):
    client = auth_client(customer)
    r = place(client, product, save_details=True)
    assert r.status_code == 201 and r.json()["account_created"] is False  # save_details is ignored for an account holder
    order = Order.objects.get()
    assert order.customer == customer and order.email == ""


# --- what the client must not control ---------------------------------------------------------------------------------------


def test_source_and_shipping_fields_from_the_client_are_ignored(api_client, product):
    r = place(api_client, product, source="call", shipping_charge="0", charge="0", zone_id=999, is_manual=True,
              created_by=1, status="delivered", grand_total="1", subtotal="1", payment_status="paid")
    assert r.status_code == 201
    order = Order.objects.get()
    assert (order.source, order.is_manual, order.created_by, order.status, order.payment_status) == ("website", False, None, "pending", "unpaid")
    assert (order.shipping_charge, order.subtotal, order.grand_total) == (D("70.00"), D("500.00"), D("570.00"))


# --- shipping (Module 9) ---------------------------------------------------------------------------------------------------------


def test_outside_dhaka_costs_120(api_client, product):
    place(api_client, product, district="Sylhet", area="")
    order = Order.objects.get()
    assert (order.shipping_zone_name, order.shipping_charge, order.grand_total) == ("Outside Dhaka", D("120.00"), D("620.00"))


def test_a_delivery_method_adds_its_extra(api_client, product):
    from apps.shipping.models import DeliveryMethod

    method = DeliveryMethod.objects.get(slug="express")
    method.is_active = True
    method.save()
    place(api_client, product, delivery_method="express")
    order = Order.objects.get()
    assert (order.shipping_charge, order.delivery_method, order.delivery_method_name) == (D("170.00"), method, "Express")


def test_an_unavailable_delivery_method_is_a_400(api_client, product):
    r = place(api_client, product, delivery_method="express")  # seeded inactive
    assert r.status_code == 400 and "delivery_method" in details(r) and Order.objects.count() == 0


def test_the_global_free_shipping_threshold_applies(api_client, product):
    set_site(free_shipping_threshold=D("1000.00"))
    place(api_client, product, quantity=2)
    order = Order.objects.get()
    assert (order.shipping_charge, order.shipping_free_reason, order.grand_total) == (D("0.00"), "free_shipping_threshold", D("1000.00"))


def test_changing_a_zone_charge_later_never_alters_existing_orders(api_client, admin_user, auth_client, product):
    place(api_client, product)
    old = Order.objects.get()
    from apps.shipping.models import DeliveryZone

    zone = DeliveryZone.objects.get(slug="inside-dhaka")
    r = auth_client(admin_user).patch(f"/api/v1/admin/shipping/zones/{zone.id}/charge/", {"charge": "999"}, format="json")
    assert r.status_code == 200
    old.refresh_from_db()
    assert (old.shipping_charge, old.grand_total, old.shipping_zone_name) == (D("70.00"), D("570.00"), "Inside Dhaka")
    api_client.credentials()  # a fresh guest
    place(api_client, ProductFactory(regular_price="500.00", stock_quantity=5), phone="01787654321")
    assert Order.objects.exclude(pk=old.pk).get().shipping_charge == D("999.00")


def test_a_zone_that_has_orders_can_no_longer_be_deleted(api_client, admin_user, auth_client, product):
    from apps.shipping.models import DeliveryZone

    place(api_client, product)
    spare = DeliveryZone.objects.get(slug="inside-dhaka")
    r = auth_client(admin_user).delete(f"/api/v1/admin/shipping/zones/{spare.id}/")
    assert r.status_code == 409 and code(r) == "zone_in_use" and DeliveryZone.objects.filter(pk=spare.pk).exists()


def test_a_delivery_method_that_has_orders_can_no_longer_be_deleted(api_client, admin_user, auth_client, product):
    from apps.shipping.models import DeliveryMethod

    standard = DeliveryMethod.objects.get(slug="standard")
    place(api_client, product, delivery_method="standard")
    r = auth_client(admin_user).delete(f"/api/v1/admin/shipping/methods/{standard.id}/")
    assert r.status_code == 409 and code(r) == "method_in_use"


# --- validation -----------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("missing", ["name", "phone", "district", "address_line"])
def test_required_fields(api_client, product, missing):
    from .helpers import add_to_cart

    add_to_cart(api_client, product)
    data = payload()
    del data[missing]
    r = api_client.post(CHECKOUT, data, format="json")
    assert r.status_code == 400 and missing in details(r) and Order.objects.count() == 0


@pytest.mark.parametrize("phone", ["12345", "0171234", "abcdefghijk", "01212345678"])
def test_a_bad_phone_is_refused(api_client, product, phone):
    r = place(api_client, product, phone=phone)
    assert r.status_code == 400 and "phone" in details(r)


def test_the_phone_is_stored_in_its_canonical_form(api_client, product):
    place(api_client, product, phone="+880 1712-345678")
    assert Order.objects.get().phone == "01712345678"


def test_a_bad_email_is_refused(api_client, product):
    assert "email" in details(place(api_client, product, email="nope"))


def test_an_empty_cart_is_a_400(api_client):
    r = api_client.post(CHECKOUT, payload(), format="json")
    assert r.status_code == 400 and "cart" in details(r)


def test_online_payment_is_not_available_yet(api_client, product):
    r = place(api_client, product, payment_method="online")
    assert r.status_code == 400 and "payment_method" in details(r) and Order.objects.count() == 0


def test_the_minimum_order_amount_is_enforced(api_client, product):
    set_site(min_order_amount=D("2000.00"))
    r = place(api_client, product)  # 500
    assert r.status_code == 400 and "minimum order amount" in details(r)["items"][0]
    assert Order.objects.count() == 0


# --- guest checkout switch -------------------------------------------------------------------------------------------------------------


def test_guest_checkout_can_be_turned_off(api_client, product):
    set_site(guest_checkout_enabled=False)
    r = place(api_client, product)
    assert r.status_code == 403 and code(r) == "guest_checkout_disabled" and "log in" in r.json()["error"]["message"]
    assert Order.objects.count() == 0


def test_customers_can_still_check_out_when_guest_checkout_is_off(auth_client, customer, product):
    set_site(guest_checkout_enabled=False)
    assert place(auth_client(customer), product).status_code == 201


def test_a_garbage_token_is_just_a_guest(api_client, product):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
    add_to_cart(api_client, product)  # cart works as a guest
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage", HTTP_X_CART_TOKEN=api_client._credentials["HTTP_X_CART_TOKEN"])
    assert api_client.post(CHECKOUT, payload(), format="json").status_code == 201


# --- stock -------------------------------------------------------------------------------------------------------------------------------


def test_stock_is_deducted_at_placement_with_an_audit_row(api_client, product):
    place(api_client, product, quantity=3)
    product.refresh_from_db()
    assert product.stock_quantity == 17
    move = StockMovement.objects.get(product=product)
    assert (move.quantity_change, move.balance_after, move.reason, move.reference) == (-3, 17, "sale", Order.objects.get().number)
    assert Order.objects.get().items.get().stock_deducted == 3


def test_ordering_more_than_is_in_stock_is_refused_and_changes_nothing(api_client):
    product = ProductFactory(stock_quantity=2, manage_stock=True)
    add_to_cart(api_client, product, quantity=2)
    product.stock_quantity = 1  # someone else bought one while it sat in the cart
    product.save()
    r = api_client.post(CHECKOUT, payload(), format="json")
    assert r.status_code == 400 and "only 1 left" in details(r)["items"][0]
    product.refresh_from_db()
    assert product.stock_quantity == 1 and Order.objects.count() == 0 and StockMovement.objects.count() == 0


def test_every_unavailable_item_is_reported_together(api_client):
    a, b = ProductFactory(stock_quantity=1), ProductFactory(stock_quantity=1)
    add_to_cart(api_client, a)
    add_to_cart(api_client, b)
    a.stock_quantity = b.stock_quantity = 0
    a.save()
    b.save()
    r = api_client.post(CHECKOUT, payload(), format="json")
    assert r.status_code == 400 and len(details(r)["items"]) == 2


def test_an_unpublished_product_cannot_be_ordered(api_client, product):
    add_to_cart(api_client, product)
    product.status = "draft"
    product.save()
    r = api_client.post(CHECKOUT, payload(), format="json")
    assert r.status_code == 400 and "items" in details(r) and Order.objects.count() == 0


def test_a_product_without_managed_stock_takes_nothing_from_stock(api_client):
    product = ProductFactory(manage_stock=False, stock_quantity=0)
    place(api_client, product, quantity=4)
    assert Order.objects.get().items.get().stock_deducted == 0 and StockMovement.objects.count() == 0


def test_unmanaged_stock_is_untouched_even_when_a_stale_stock_number_is_left_on_the_product(api_client):
    """`manage_stock=False` means "don't count", whatever stock_quantity happens to still say."""
    product = ProductFactory(manage_stock=False, stock_quantity=10)
    assert place(api_client, product, quantity=4).status_code == 201
    product.refresh_from_db()
    assert product.stock_quantity == 10 and StockMovement.objects.count() == 0
    assert Order.objects.get().items.get().stock_deducted == 0


def test_a_backorder_product_sells_past_zero_but_only_takes_what_is_on_the_shelf(api_client):
    product = ProductFactory(stock_quantity=2, manage_stock=True, stock_status="backorder")
    place(api_client, product, quantity=5)
    product.refresh_from_db()
    assert product.stock_quantity == 0 and Order.objects.get().items.get().stock_deducted == 2


def test_variant_products_deduct_the_variants_stock(api_client):
    from apps.catalog.tests.factories import ProductVariantFactory

    product = ProductFactory(has_variants=True, stock_quantity=0)
    variant = ProductVariantFactory(product=product, stock_quantity=10, regular_price="300.00")
    add_to_cart(api_client, product, quantity=2, variant=variant)
    assert api_client.post(CHECKOUT, payload(), format="json").status_code == 201
    variant.refresh_from_db()
    item = Order.objects.get().items.get()
    assert variant.stock_quantity == 8 and item.variant == variant and item.sku == variant.sku and item.unit_price == D("300.00")


# --- coupons ---------------------------------------------------------------------------------------------------------------------------------


def test_the_coupon_applied_to_the_cart_is_used(api_client, product):
    add_to_cart(api_client, product, quantity=2)
    CouponFactory(code="SAVE100", amount="100.00")
    api_client.post(CART_COUPON, {"code": "SAVE100"}, format="json")
    assert api_client.post(CHECKOUT, payload(), format="json").status_code == 201
    order = Order.objects.get()
    assert (order.coupon_code, order.discount_amount, order.grand_total) == ("SAVE100", D("100.00"), D("970.00"))  # 1000-100+70
    usage = CouponUsage.objects.get()
    assert (usage.order_reference, usage.phone, usage.discount_amount) == (order.number, "01712345678", D("100.00"))


def test_a_coupon_typed_at_checkout_is_used(api_client, product):
    CouponFactory(code="TEN", type="percentage", amount="10.00")
    r = place(api_client, product, quantity=2, coupon="ten")
    assert r.status_code == 201 and Order.objects.get().discount_amount == D("100.00")


def test_an_invalid_typed_coupon_is_a_400_and_nothing_is_created(api_client, product):
    r = place(api_client, product, coupon="NOPE")
    assert r.status_code == 400 and "coupon" in details(r) and Order.objects.count() == 0
    product.refresh_from_db()
    assert product.stock_quantity == 20


def test_a_cart_coupon_that_stopped_applying_is_dropped_not_an_error(api_client, product):
    add_to_cart(api_client, product)
    coupon = CouponFactory(code="SAVE50", amount="50.00")
    api_client.post(CART_COUPON, {"code": "SAVE50"}, format="json")
    coupon.is_active = False
    coupon.save()
    assert api_client.post(CHECKOUT, payload(), format="json").status_code == 201
    order = Order.objects.get()
    assert order.coupon is None and order.discount_amount == 0 and CouponUsage.objects.count() == 0


def test_a_free_shipping_coupon_zeroes_the_delivery_charge(api_client, product):
    CouponFactory(code="SHIPFREE", amount="10.00", free_shipping=True)
    place(api_client, product, coupon="SHIPFREE")
    order = Order.objects.get()
    assert (order.shipping_charge, order.shipping_free_reason, order.grand_total) == (D("0.00"), "coupon_free_shipping", D("490.00"))


def test_the_per_customer_limit_counts_earlier_orders_by_phone(api_client, product):
    CouponFactory(code="ONCE", amount="10.00", per_customer_usage_limit=1)
    assert place(api_client, product, coupon="ONCE").status_code == 201
    api_client.credentials()
    other = ProductFactory(regular_price="600.00", stock_quantity=5)
    r = place(api_client, other, coupon="ONCE")
    assert r.status_code == 400 and "coupon" in details(r) and Order.objects.count() == 1


def test_a_first_order_only_coupon_refuses_a_returning_customer(api_client, product):
    place(api_client, product)  # their first order, no coupon
    api_client.credentials()
    CouponFactory(code="WELCOME", amount="10.00", first_order_only=True)
    other = ProductFactory(regular_price="600.00", stock_quantity=5)
    r = place(api_client, other, coupon="WELCOME")
    assert r.status_code == 400 and "first order" in details(r)["coupon"][0]


def test_a_first_order_only_coupon_works_for_a_new_customer(api_client, product):
    CouponFactory(code="WELCOME", amount="10.00", first_order_only=True)
    assert place(api_client, product, coupon="WELCOME").status_code == 201


def test_a_cancelled_first_order_does_not_count_against_first_order_only(api_client, product, admin_user, auth_client):
    place(api_client, product)
    from apps.orders import services

    services.change_status(Order.objects.get(), "cancelled", user=admin_user)
    api_client.credentials()
    CouponFactory(code="WELCOME", amount="10.00", first_order_only=True)
    other = ProductFactory(regular_price="600.00", stock_quantity=5)
    assert place(api_client, other, coupon="WELCOME").status_code == 201


def test_a_failed_checkout_leaves_the_coupon_unused(api_client):
    scarce = ProductFactory(stock_quantity=1)
    add_to_cart(api_client, scarce)
    coupon = CouponFactory(code="SAVE50", amount="50.00", total_usage_limit=1)
    api_client.post(CART_COUPON, {"code": "SAVE50"}, format="json")
    scarce.stock_quantity = 0
    scarce.save()
    assert api_client.post(CHECKOUT, payload(), format="json").status_code == 400
    assert CouponUsage.objects.filter(coupon=coupon).count() == 0
