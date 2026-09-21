from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.exceptions import Conflict
from apps.catalog.models import StockMovement
from apps.catalog.tests.factories import ProductFactory
from apps.coupons.models import CouponUsage
from apps.coupons.tests.factories import CouponFactory
from apps.orders import services
from apps.orders.models import Order, OrderStatus, OrderStatusHistory

from .helpers import new_order

pytestmark = pytest.mark.django_db

ALL = [s.value for s in OrderStatus]
FLOW = {
    "pending": {"confirmed", "cancelled", "failed"},
    "confirmed": {"processing", "cancelled", "failed"},
    "processing": {"shipped", "cancelled", "failed"},
    "shipped": {"delivered", "returned", "failed"},
    "delivered": {"returned"},
    "cancelled": set(), "returned": set(), "failed": set(),
}


def in_status(order, status):
    Order.objects.filter(pk=order.pk).update(status=status)
    order.refresh_from_db()
    return order


# --- the machine, exhaustively ------------------------------------------------------------------------------------------------


def test_the_documented_flow_is_exactly_what_the_service_allows():
    assert {k.value: {v.value for v in vs} for k, vs in services.TRANSITIONS.items()} == FLOW


@pytest.mark.parametrize("old", ALL)
@pytest.mark.parametrize("new", ALL)
def test_every_pair_of_statuses(admin_user, old, new):
    order = in_status(new_order(admin_user), old)
    if new in FLOW[old]:
        assert services.change_status(order, new, user=admin_user).status == new
    else:
        with pytest.raises(ValidationError) as exc:
            services.change_status(order, new, user=admin_user)
        assert "status" in exc.value.message_dict
        order.refresh_from_db()
        assert order.status == old  # a refused change changes nothing


def test_the_happy_path_end_to_end_with_history(admin_user, cce_user):
    order = new_order(admin_user)
    for user, status in [(cce_user, "confirmed"), (cce_user, "processing"), (admin_user, "shipped"), (admin_user, "delivered")]:
        services.change_status(order, status, user=user, note=f"to {status}")
    rows = list(OrderStatusHistory.objects.filter(order=order))
    assert [(r.from_status, r.to_status) for r in rows] == [
        ("", "pending"), ("pending", "confirmed"), ("confirmed", "processing"), ("processing", "shipped"), ("shipped", "delivered")]
    assert rows[1].changed_by == cce_user and rows[1].note == "to confirmed" and rows[3].changed_by == admin_user


def test_the_error_names_the_allowed_next_statuses(admin_user):
    order = new_order(admin_user)
    with pytest.raises(ValidationError) as exc:
        services.change_status(order, "delivered", user=admin_user)
    error = exc.value.error_dict["status"][0]
    assert error.code == "invalid_transition" and "confirmed" in error.message and "cancelled" in error.message


def test_changing_to_the_same_status_is_refused(admin_user):
    with pytest.raises(ValidationError) as exc:
        services.change_status(new_order(admin_user), "pending", user=admin_user)
    assert exc.value.error_dict["status"][0].code == "same_status"


def test_final_statuses_cannot_be_left(admin_user):
    for final in ("cancelled", "returned", "failed"):
        order = in_status(new_order(admin_user), final)
        with pytest.raises(ValidationError) as exc:
            services.change_status(order, "pending", user=admin_user)
        assert "final" in exc.value.error_dict["status"][0].message


def test_courier_details_are_saved_with_the_status_change(admin_user):
    order = new_order(admin_user)
    in_status(order, "processing")
    services.change_status(order, "shipped", user=admin_user, courier={"courier_name": "Pathao", "tracking_id": "T-1", "consignment_id": ""})
    order.refresh_from_db()
    assert (order.courier_name, order.tracking_id, order.consignment_id) == ("Pathao", "T-1", "")


# --- stock ----------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("ending", ["cancelled", "failed", "returned"])
def test_cancel_fail_and_return_put_the_stock_back(admin_user, ending):
    product = ProductFactory(stock_quantity=10, manage_stock=True)
    order = new_order(admin_user, product=product, quantity=4)
    product.refresh_from_db()
    assert product.stock_quantity == 6
    in_status(order, "shipped" if ending == "returned" else "pending")
    services.change_status(order, ending, user=admin_user)
    product.refresh_from_db()
    assert product.stock_quantity == 10
    back = StockMovement.objects.filter(product=product, reason="return").get()
    assert (back.quantity_change, back.reference, back.user) == (4, order.number, admin_user)
    assert Order.objects.get(pk=order.pk).stock_released_at is not None


@pytest.mark.parametrize("status", ["confirmed", "processing", "shipped", "delivered"])
def test_moving_forward_never_touches_stock(admin_user, status):
    product = ProductFactory(stock_quantity=10, manage_stock=True)
    order = new_order(admin_user, product=product, quantity=4)
    in_status(order, {"confirmed": "pending", "processing": "confirmed", "shipped": "processing", "delivered": "shipped"}[status])
    services.change_status(order, status, user=admin_user)
    product.refresh_from_db()
    assert product.stock_quantity == 6


def test_stock_is_restored_only_once(admin_user):
    product = ProductFactory(stock_quantity=10, manage_stock=True)
    order = new_order(admin_user, product=product, quantity=4)
    services.change_status(order, "cancelled", user=admin_user)
    services._restore_stock(Order.objects.get(pk=order.pk), "again", admin_user)  # a second release must be a no-op
    product.refresh_from_db()
    assert product.stock_quantity == 10 and StockMovement.objects.filter(reason="return").count() == 1


def test_a_backorder_line_restores_only_what_it_took(admin_user):
    product = ProductFactory(stock_quantity=2, manage_stock=True, stock_status="backorder")
    order = new_order(admin_user, product=product, quantity=5)  # took 2, owes 3
    services.change_status(order, "cancelled", user=admin_user)
    product.refresh_from_db()
    assert product.stock_quantity == 2  # not 5


def test_unmanaged_stock_is_left_alone(admin_user):
    product = ProductFactory(manage_stock=False, stock_quantity=0)
    order = new_order(admin_user, product=product, quantity=3)
    services.change_status(order, "cancelled", user=admin_user)
    product.refresh_from_db()
    assert product.stock_quantity == 0 and StockMovement.objects.count() == 0


def test_a_deleted_product_does_not_break_cancelling(admin_user):
    product = ProductFactory(stock_quantity=10, manage_stock=True)
    order = new_order(admin_user, product=product, quantity=2)
    product.hard_delete()
    assert services.change_status(order, "cancelled", user=admin_user).status == "cancelled"


def test_stock_that_stopped_being_managed_does_not_break_cancelling(admin_user):
    product = ProductFactory(stock_quantity=10, manage_stock=True)
    order = new_order(admin_user, product=product, quantity=2)
    product.manage_stock = False
    product.save()
    assert services.change_status(order, "cancelled", user=admin_user).status == "cancelled"


# --- coupons ----------------------------------------------------------------------------------------------------------------------------------


@pytest.fixture
def coupon_order(admin_user):
    CouponFactory(code="SAVE50", amount="50.00")
    return new_order(admin_user, coupon="SAVE50")


def test_a_cancelled_or_failed_order_releases_its_coupon_use(admin_user, coupon_order):
    assert CouponUsage.objects.count() == 1
    services.change_status(coupon_order, "cancelled", user=admin_user)
    assert CouponUsage.objects.count() == 0


def test_a_failed_order_releases_its_coupon_use(admin_user, coupon_order):
    services.change_status(coupon_order, "failed", user=admin_user)
    assert CouponUsage.objects.count() == 0


def test_a_returned_order_keeps_its_coupon_use(admin_user, coupon_order):
    in_status(coupon_order, "delivered")
    services.change_status(coupon_order, "returned", user=admin_user)
    assert CouponUsage.objects.count() == 1  # the discount was really given


def test_a_released_coupon_can_be_used_again(admin_user):
    coupon = CouponFactory(code="ONCE", amount="10.00", total_usage_limit=1)
    first = new_order(admin_user, coupon="ONCE")
    services.change_status(first, "cancelled", user=admin_user)
    assert new_order(admin_user, coupon="ONCE", phone="01787654321").coupon == coupon


# --- customer cancellation -------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_a_customer_can_cancel_early(customer, status):
    order = in_status(new_order(customer=customer), status)
    assert services.cancel_by_customer(order, customer).status == "cancelled"
    assert OrderStatusHistory.objects.filter(order=order).last().changed_by == customer


@pytest.mark.parametrize("status", ["processing", "shipped", "delivered", "cancelled", "returned", "failed"])
def test_a_customer_cannot_cancel_later(customer, status):
    order = in_status(new_order(customer=customer), status)
    with pytest.raises(Conflict) as exc:
        services.cancel_by_customer(order, customer)
    assert exc.value.get_codes() == "not_cancellable"


# --- deleting ---------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["cancelled", "failed", "returned"])
def test_only_finished_orders_can_be_deleted(admin_user, status):
    order = in_status(new_order(admin_user), status)
    services.delete_order(order)
    assert not Order.objects.filter(pk=order.pk).exists() and Order.all_objects.filter(pk=order.pk).exists()  # soft delete


@pytest.mark.parametrize("status", ["pending", "confirmed", "processing", "shipped", "delivered"])
def test_a_live_order_cannot_be_deleted(admin_user, status):
    order = in_status(new_order(admin_user), status)
    with pytest.raises(Conflict) as exc:
        services.delete_order(order)
    assert exc.value.get_codes() == "order_not_deletable"


# --- the shipping override, at the service level (the API validates first, so test the guard itself) -------------------------


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_the_service_itself_refuses_an_override_without_a_reason(admin_user, reason):
    order = new_order(admin_user)
    with pytest.raises(ValidationError) as exc:
        services.override_shipping(order, charge="10", reason=reason, user=admin_user)
    assert exc.value.error_dict["reason"][0].code == "reason_required"
    assert Order.objects.get(pk=order.pk).shipping_charge == Decimal("70.00")
