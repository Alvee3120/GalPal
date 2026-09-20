import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.cart import services as cart_services
from apps.cart.tests.factories import CartFactory, CartItemFactory
from apps.catalog import services as catalog_services
from apps.catalog.tests.factories import BrandFactory, CategoryFactory, ProductFactory
from apps.coupons import services
from apps.coupons.models import Coupon, CouponUsage

from .factories import CouponFactory, CouponUsageFactory

pytestmark = pytest.mark.django_db


def code_of(exc, field):
    return exc.value.error_dict[field][0].code


def cart_with(*lines):
    """lines: (price, quantity, product_kwargs). Returns (cart, summary rows, subtotal)."""
    cart = CartFactory()
    for price, quantity, extra in lines:
        product = ProductFactory(regular_price=price, stock_quantity=100, **extra)
        CartItemFactory(cart=cart, product=product, quantity=quantity)
    summary = cart_services.summarize(cart)
    return cart, summary["rows"], summary["subtotal"]


def discount_for(coupon, *lines):
    _, rows, _ = cart_with(*lines)
    return services.compute_discount(coupon, rows)


# --- compute_discount ----------------------------------------------------------------------------


def test_flat_discount():
    assert discount_for(CouponFactory(type="flat", amount="100.00"), ("1000.00", 1, {})) == Decimal("100.00")


def test_flat_discount_never_exceeds_the_eligible_subtotal():
    assert discount_for(CouponFactory(type="flat", amount="500.00"), ("200.00", 1, {})) == Decimal("200.00")


def test_percentage_discount():
    assert discount_for(CouponFactory(type="percentage", amount="10.00"), ("1000.00", 1, {})) == Decimal("100.00")


def test_percentage_discount_is_capped_by_max_discount_amount():
    coupon = CouponFactory(type="percentage", amount="20.00", max_discount_amount="150.00")
    assert discount_for(coupon, ("2000.00", 1, {})) == Decimal("150.00")


def test_percentage_cap_does_not_inflate_a_smaller_discount():
    coupon = CouponFactory(type="percentage", amount="10.00", max_discount_amount="500.00")
    assert discount_for(coupon, ("1000.00", 1, {})) == Decimal("100.00")


def test_percentage_rounds_half_up_to_the_cent():
    coupon = CouponFactory(type="percentage", amount="10.00")
    # 3.325 sits exactly on a half: half-up gives 3.33, banker's rounding (half-even) would give 3.32
    assert discount_for(coupon, ("33.25", 1, {})) == Decimal("3.33")


def test_discount_is_zero_for_an_empty_or_ineligible_cart():
    assert services.compute_discount(CouponFactory(), []) == Decimal("0.00")


def test_unavailable_lines_are_not_discounted():
    cart = CartFactory()
    CartItemFactory(cart=cart, product=ProductFactory(regular_price="500.00", stock_quantity=10), quantity=1)
    CartItemFactory(cart=cart, product=ProductFactory(regular_price="500.00", status="draft"), quantity=1)
    coupon = CouponFactory(type="percentage", amount="50.00")
    assert services.compute_discount(coupon, cart_services.summarize(cart)["rows"]) == Decimal("250.00")


# --- applicability -------------------------------------------------------------------------------------


def test_product_restriction_only_discounts_matching_lines():
    cart = CartFactory()
    target = ProductFactory(regular_price="1000.00", stock_quantity=10)
    other = ProductFactory(regular_price="1000.00", stock_quantity=10)
    CartItemFactory(cart=cart, product=target, quantity=1)
    CartItemFactory(cart=cart, product=other, quantity=1)
    coupon = CouponFactory(type="percentage", amount="10.00")
    coupon.products.set([target])
    assert services.compute_discount(coupon, cart_services.summarize(cart)["rows"]) == Decimal("100.00")


def test_category_restriction():
    cart = CartFactory()
    category = CategoryFactory()
    inside, outside = ProductFactory(regular_price="400.00", stock_quantity=5), ProductFactory(regular_price="400.00", stock_quantity=5)
    catalog_services.set_categories(inside, [category.id])
    CartItemFactory(cart=cart, product=inside, quantity=1)
    CartItemFactory(cart=cart, product=outside, quantity=1)
    coupon = CouponFactory(type="percentage", amount="50.00")
    coupon.categories.set([category])
    assert services.compute_discount(coupon, cart_services.summarize(cart)["rows"]) == Decimal("200.00")


def test_category_restriction_includes_sub_categories():
    """Regression (found live): a coupon on "Skincare" must cover products filed under "Skincare > Serums",
    matching how the public category filter already treats descendants."""
    cart = CartFactory()
    parent = CategoryFactory()
    child = CategoryFactory(parent=parent)
    grandchild = CategoryFactory(parent=child)
    unrelated = CategoryFactory()
    for category in (child, grandchild):
        product = ProductFactory(regular_price="100.00", stock_quantity=5)
        catalog_services.set_categories(product, [category.id])
        CartItemFactory(cart=cart, product=product, quantity=1)
    outside = ProductFactory(regular_price="100.00", stock_quantity=5)
    catalog_services.set_categories(outside, [unrelated.id])
    CartItemFactory(cart=cart, product=outside, quantity=1)
    coupon = CouponFactory(type="percentage", amount="50.00")
    coupon.categories.set([parent])  # only the top-level category is selected
    assert services.compute_discount(coupon, cart_services.summarize(cart)["rows"]) == Decimal("100.00")  # 50% of 200


def test_category_restriction_does_not_leak_upwards():
    """Selecting a child category must not discount products filed only under its parent."""
    cart = CartFactory()
    parent = CategoryFactory()
    child = CategoryFactory(parent=parent)
    product = ProductFactory(regular_price="100.00", stock_quantity=5)
    catalog_services.set_categories(product, [parent.id])
    CartItemFactory(cart=cart, product=product, quantity=1)
    coupon = CouponFactory(type="percentage", amount="50.00")
    coupon.categories.set([child])
    assert services.compute_discount(coupon, cart_services.summarize(cart)["rows"]) == Decimal("0.00")


def test_brand_restriction():
    cart = CartFactory()
    brand = BrandFactory()
    CartItemFactory(cart=cart, product=ProductFactory(regular_price="300.00", stock_quantity=5, brand=brand), quantity=1)
    CartItemFactory(cart=cart, product=ProductFactory(regular_price="300.00", stock_quantity=5), quantity=1)
    coupon = CouponFactory(type="percentage", amount="10.00")
    coupon.brands.set([brand])
    assert services.compute_discount(coupon, cart_services.summarize(cart)["rows"]) == Decimal("30.00")


def test_restrictions_are_a_union_not_an_intersection():
    cart = CartFactory()
    brand, category = BrandFactory(), CategoryFactory()
    by_brand = ProductFactory(regular_price="100.00", stock_quantity=5, brand=brand)
    by_category = ProductFactory(regular_price="100.00", stock_quantity=5)
    catalog_services.set_categories(by_category, [category.id])
    neither = ProductFactory(regular_price="100.00", stock_quantity=5)
    for product in (by_brand, by_category, neither):
        CartItemFactory(cart=cart, product=product, quantity=1)
    coupon = CouponFactory(type="percentage", amount="50.00")
    coupon.brands.set([brand])
    coupon.categories.set([category])
    assert services.compute_discount(coupon, cart_services.summarize(cart)["rows"]) == Decimal("100.00")  # 50% of 200


def test_exclude_sale_items():
    cart = CartFactory()
    CartItemFactory(cart=cart, product=ProductFactory(regular_price="1000.00", discount_price="800.00", stock_quantity=5), quantity=1)
    CartItemFactory(cart=cart, product=ProductFactory(regular_price="500.00", stock_quantity=5), quantity=1)
    coupon = CouponFactory(type="percentage", amount="10.00", exclude_sale_items=True)
    assert services.compute_discount(coupon, cart_services.summarize(cart)["rows"]) == Decimal("50.00")  # only the 500 item


# --- evaluate ---------------------------------------------------------------------------------------------


def evaluate(coupon, *lines, user=None, phone=None):
    _, rows, subtotal = cart_with(*(lines or [("1000.00", 1, {})]))
    return services.evaluate(coupon, subtotal=subtotal, rows=rows, user=user, phone=phone)


def test_evaluate_valid():
    ok, message, discount = evaluate(CouponFactory(amount="100.00"))
    assert ok and message == "" and discount == Decimal("100.00")


def test_evaluate_inactive():
    ok, message, discount = evaluate(CouponFactory(is_active=False))
    assert not ok and "not active" in message and discount == Decimal("0.00")


def test_evaluate_schedule_window():
    now = timezone.now()
    assert not evaluate(CouponFactory(start_at=now + timedelta(days=1)))[0]  # not started
    assert not evaluate(CouponFactory(expiry_at=now - timedelta(days=1)))[0]  # expired
    assert evaluate(CouponFactory(start_at=now - timedelta(days=1), expiry_at=now + timedelta(days=1)))[0]


def test_evaluate_min_order_uses_the_whole_cart_not_just_eligible_lines():
    cart = CartFactory()
    target = ProductFactory(regular_price="200.00", stock_quantity=5)
    CartItemFactory(cart=cart, product=target, quantity=1)
    CartItemFactory(cart=cart, product=ProductFactory(regular_price="900.00", stock_quantity=5), quantity=1)
    coupon = CouponFactory(min_order_amount="1000.00", type="percentage", amount="10.00")
    coupon.products.set([target])
    summary = cart_services.summarize(cart)
    ok, _, discount = services.evaluate(coupon, subtotal=summary["subtotal"], rows=summary["rows"])
    assert ok and discount == Decimal("20.00")  # subtotal 1100 >= 1000, but only 200 is discounted


def test_evaluate_min_order_not_met():
    ok, message, _ = evaluate(CouponFactory(min_order_amount="5000.00"))
    assert not ok and "Minimum order amount" in message


def test_evaluate_total_usage_limit():
    coupon = CouponFactory(total_usage_limit=2)
    CouponUsageFactory.create_batch(2, coupon=coupon)
    ok, message, _ = evaluate(coupon)
    assert not ok and "usage limit" in message


def test_evaluate_per_user_limit_only_counts_that_user():
    user, other = UserFactory(), UserFactory()
    coupon = CouponFactory(per_customer_usage_limit=1)
    CouponUsageFactory(coupon=coupon, user=user, phone=user.phone)
    assert not evaluate(coupon, user=user)[0]
    assert evaluate(coupon, user=other)[0]


def test_evaluate_per_phone_limit_for_guests():
    coupon = CouponFactory(per_customer_usage_limit=1)
    CouponUsageFactory(coupon=coupon, phone="01711111111")
    assert not evaluate(coupon, phone="01711111111")[0]
    assert evaluate(coupon, phone="01822222222")[0]


def test_evaluate_reports_a_coupon_that_matches_nothing():
    coupon = CouponFactory()
    coupon.products.set([ProductFactory()])  # a product that isn't in the cart
    ok, message, _ = evaluate(coupon)
    assert not ok and "does not apply" in message


def test_evaluate_never_raises():
    assert services.evaluate(CouponFactory(), subtotal=Decimal("0"), rows=[])[0] is False


# --- apply / remove --------------------------------------------------------------------------------------------


def test_apply_attaches_the_coupon_case_insensitively():
    cart, _, _ = cart_with(("1000.00", 1, {}))
    CouponFactory(code="WELCOME")
    coupon = services.apply_coupon_to_cart(cart, "  welcome ")
    cart.refresh_from_db()
    assert cart.coupon == coupon


def test_apply_unknown_code():
    cart, _, _ = cart_with(("1000.00", 1, {}))
    with pytest.raises(ValidationError) as exc:
        services.apply_coupon_to_cart(cart, "NOPE")
    assert code_of(exc, "code") == "not_found"


def test_apply_rejects_a_coupon_that_does_not_currently_work():
    cart, _, _ = cart_with(("100.00", 1, {}))
    CouponFactory(code="BIG", min_order_amount="5000.00")
    with pytest.raises(ValidationError) as exc:
        services.apply_coupon_to_cart(cart, "BIG")
    assert code_of(exc, "code") == "coupon_not_applicable"
    cart.refresh_from_db()
    assert cart.coupon is None


def test_apply_replaces_a_previous_coupon():
    cart, _, _ = cart_with(("1000.00", 1, {}))
    CouponFactory(code="ONE"), CouponFactory(code="TWO")
    services.apply_coupon_to_cart(cart, "ONE")
    services.apply_coupon_to_cart(cart, "TWO")
    cart.refresh_from_db()
    assert cart.coupon.code == "TWO"


def test_a_failed_apply_keeps_the_previous_coupon():
    cart, _, _ = cart_with(("100.00", 1, {}))
    CouponFactory(code="OK", amount="10.00")
    CouponFactory(code="TOOBIG", min_order_amount="9999.00")
    services.apply_coupon_to_cart(cart, "OK")
    with pytest.raises(ValidationError):
        services.apply_coupon_to_cart(cart, "TOOBIG")
    cart.refresh_from_db()
    assert cart.coupon.code == "OK"


def test_remove():
    cart, _, _ = cart_with(("1000.00", 1, {}))
    CouponFactory(code="ONE")
    services.apply_coupon_to_cart(cart, "ONE")
    services.remove_coupon_from_cart(cart)
    cart.refresh_from_db()
    assert cart.coupon is None
    services.remove_coupon_from_cart(cart)  # idempotent


def test_apply_enforces_the_per_user_limit_for_a_logged_in_customer():
    user = UserFactory()
    cart, _, _ = cart_with(("1000.00", 1, {}))
    coupon = CouponFactory(code="ONCE", per_customer_usage_limit=1)
    CouponUsageFactory(coupon=coupon, user=user, phone=user.phone)
    with pytest.raises(ValidationError):
        services.apply_coupon_to_cart(cart, "ONCE", user=user)


# --- redeem_coupon -------------------------------------------------------------------------------------------------


def test_redeem_records_a_usage():
    user = UserFactory()
    coupon = CouponFactory()
    usage = services.redeem_coupon(coupon, phone=user.phone, user=user, order_reference="ORD-1", discount_amount="100.00")
    assert usage.pk and usage.user == user and usage.phone == user.phone and usage.discount_amount == Decimal("100.00")


def test_redeem_enforces_total_limit():
    coupon = CouponFactory(total_usage_limit=1)
    services.redeem_coupon(coupon, phone="01711111111", order_reference="A", discount_amount="10.00")
    with pytest.raises(ValidationError) as exc:
        services.redeem_coupon(coupon, phone="01822222222", order_reference="B", discount_amount="10.00")
    assert code_of(exc, "coupon") == "usage_limit_reached"
    assert CouponUsage.objects.count() == 1


def test_redeem_enforces_per_customer_limit_by_user_and_by_phone():
    coupon = CouponFactory(per_customer_usage_limit=1)
    user = UserFactory()
    services.redeem_coupon(coupon, phone=user.phone, user=user, order_reference="A", discount_amount="10.00")
    with pytest.raises(ValidationError) as exc:
        services.redeem_coupon(coupon, phone=user.phone, user=user, order_reference="B", discount_amount="10.00")
    assert code_of(exc, "coupon") == "per_customer_limit_reached"
    services.redeem_coupon(coupon, phone="01711111111", order_reference="C", discount_amount="10.00")
    with pytest.raises(ValidationError):
        services.redeem_coupon(coupon, phone="01711111111", order_reference="D", discount_amount="10.00")


def test_redeem_rejects_an_inactive_or_expired_coupon():
    for coupon in (CouponFactory(is_active=False), CouponFactory(expiry_at=timezone.now() - timedelta(minutes=1))):
        with pytest.raises(ValidationError) as exc:
            services.redeem_coupon(coupon, phone="01711111111", order_reference="X", discount_amount="1.00")
        assert code_of(exc, "coupon") == "coupon_invalid"


def test_redeem_rechecks_the_live_row_not_the_instance_passed_in():
    coupon = CouponFactory()
    stale = Coupon.objects.get(pk=coupon.pk)
    Coupon.objects.filter(pk=coupon.pk).update(is_active=False)  # deactivated after the caller loaded it
    with pytest.raises(ValidationError):
        services.redeem_coupon(stale, phone="01711111111", order_reference="X", discount_amount="1.00")


# --- concurrency: the spec's "limits can't be exceeded by concurrent requests" ------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_redemptions_cannot_exceed_the_total_limit():
    coupon = CouponFactory(total_usage_limit=3)
    attempts, barrier = 10, threading.Barrier(10)

    def redeem(i):
        try:
            barrier.wait(timeout=10)
            services.redeem_coupon(coupon, phone=f"017000000{i:02d}", order_reference=f"ORD-{i}", discount_amount="10.00")
            return "ok"
        except ValidationError:
            return "rejected"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=attempts) as pool:
        results = list(pool.map(redeem, range(attempts)))
    assert results.count("ok") == 3 and results.count("rejected") == 7
    assert CouponUsage.objects.filter(coupon=coupon).count() == 3


@pytest.mark.django_db(transaction=True)
def test_concurrent_redemptions_cannot_exceed_the_per_customer_limit():
    coupon = CouponFactory(per_customer_usage_limit=1)
    attempts, barrier = 6, threading.Barrier(6)

    def redeem(i):
        try:
            barrier.wait(timeout=10)
            services.redeem_coupon(coupon, phone="01711111111", order_reference=f"ORD-{i}", discount_amount="10.00")
            return "ok"
        except ValidationError:
            return "rejected"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=attempts) as pool:
        results = list(pool.map(redeem, range(attempts)))
    assert results.count("ok") == 1
    assert CouponUsage.objects.filter(coupon=coupon, phone="01711111111").count() == 1
