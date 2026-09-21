from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import AddressFactory, UserFactory
from apps.catalog.models import StockMovement
from apps.catalog.tests.factories import ProductFactory, ProductVariantFactory
from apps.coupons.models import CouponUsage
from apps.coupons.tests.factories import CouponFactory
from apps.orders import services
from apps.orders.models import Order, OrderNote

from .conftest import set_site
from .helpers import code, details, new_order

pytestmark = pytest.mark.django_db

D = Decimal
ORDERS = "/api/v1/admin/orders/"


def url(order, suffix=""):
    return f"{ORDERS}{order.id}/{suffix}"


def manual(items, **overrides):
    body = {"name": "Rina Akter", "phone": "01712345678", "district": "Dhaka", "address_line": "House 4", "source": "call",
            "items": items}
    body.update(overrides)
    return body


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


@pytest.fixture
def cce_client(auth_client, cce_user):
    return auth_client(cce_user)


# --- who may do what -----------------------------------------------------------------------------------------------------------


@pytest.fixture
def order(admin_user):
    return new_order(admin_user)


def every_order_route(order):
    return [
        ("get", ORDERS), ("post", ORDERS), ("get", url(order)), ("patch", url(order)), ("delete", url(order)),
        ("post", url(order, "status/")), ("get", url(order, "notes/")), ("post", url(order, "notes/")),
        ("get", url(order, "invoice/")), ("post", url(order, "shipping-override/")),
        ("get", f"{ORDERS}helpers/products/"), ("get", f"{ORDERS}helpers/shipping/"), ("get", f"{ORDERS}helpers/customers/"),
    ]


def test_anonymous_gets_401_everywhere(api_client, order):
    for verb, path in every_order_route(order):
        assert getattr(api_client, verb)(path, {}, format="json").status_code == 401, (verb, path)


def test_customers_get_403_everywhere(auth_client, customer, order):
    client = auth_client(customer)
    for verb, path in every_order_route(order):
        assert getattr(client, verb)(path, {}, format="json").status_code == 403, (verb, path)


def test_an_inactive_cce_is_locked_out(auth_client, cce_user, order):
    client = auth_client(cce_user)
    cce_user.is_active = False
    cce_user.save()
    assert client.get(ORDERS).status_code == 401


ADMIN_ONLY = [("delete", ""), ("post", "shipping-override/")]


@pytest.mark.parametrize(("verb", "suffix"), ADMIN_ONLY)
def test_a_cce_cannot_delete_orders_or_override_shipping(cce_client, admin_user, verb, suffix):
    order = services.change_status(new_order(admin_user), "cancelled", user=admin_user)
    r = getattr(cce_client, verb)(url(order, suffix), {"charge": "1", "reason": "x"}, format="json")
    assert r.status_code == 403 and Order.objects.filter(pk=order.pk).exists()
    assert Order.objects.get(pk=order.pk).shipping_charge == D("70.00")


def test_a_cce_can_do_the_whole_order_job(cce_client, product):
    """Everything the spec lets a CCE do, end to end: create, view, note, edit while pending, change status, invoice, helpers."""
    made = cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 1}]), format="json")
    assert made.status_code == 201
    oid = made.json()["order"]["id"]
    assert cce_client.get(ORDERS).status_code == 200 and cce_client.get(f"{ORDERS}{oid}/").status_code == 200
    assert cce_client.post(f"{ORDERS}{oid}/notes/", {"text": "called"}, format="json").status_code == 201
    assert cce_client.patch(f"{ORDERS}{oid}/", {"note": "leave at gate"}, format="json").status_code == 200
    assert cce_client.post(f"{ORDERS}{oid}/status/", {"status": "confirmed"}, format="json").status_code == 200
    assert cce_client.get(f"{ORDERS}{oid}/invoice/").status_code == 200
    assert cce_client.get(f"{ORDERS}helpers/products/").status_code == 200


def test_an_admin_can_delete_a_finished_order_and_override_shipping(admin_client, admin_user):
    live = new_order(admin_user)
    assert admin_client.post(url(live, "shipping-override/"), {"charge": "10", "reason": "goodwill"}, format="json").status_code == 200
    services.change_status(live, "cancelled", user=admin_user)
    assert admin_client.delete(url(live)).status_code == 204


# --- creating a manual order -----------------------------------------------------------------------------------------------------


def test_a_manual_order_records_source_staff_and_manual_flag(cce_client, cce_user, product):
    r = cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 2}], source="facebook", source_note="Ad campaign X", note="ring first"), format="json")
    assert r.status_code == 201, r.json()
    body = r.json()
    order = Order.objects.get()
    assert (order.source, order.source_note, order.is_manual, order.created_by, order.customer, order.status) == (
        "facebook", "Ad campaign X", True, cce_user, None, "pending")
    assert body["order"]["source"] == "facebook" and body["order"]["is_manual"] is True
    assert body["order"]["created_by"] == {"id": cce_user.id, "full_name": cce_user.full_name} and body["warnings"] == []
    assert (order.subtotal, order.shipping_charge, order.grand_total) == (D("1000.00"), D("70.00"), D("1070.00"))


@pytest.mark.parametrize("source", ["website", "facebook", "instagram", "tiktok", "whatsapp", "messenger", "call", "other"])
def test_every_documented_source_is_accepted(cce_client, product, source):
    r = cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 1}], source=source), format="json")
    assert r.status_code == 201 and Order.objects.get().source == source


def test_source_is_required_and_must_be_one_of_the_choices(cce_client, product):
    items = [{"product_id": product.id, "quantity": 1}]
    body = manual(items)
    del body["source"]
    r = cce_client.post(ORDERS, body, format="json")
    assert r.status_code == 400 and "source" in details(r)
    assert "source" in details(cce_client.post(ORDERS, manual(items, source="carrier-pigeon"), format="json"))
    assert Order.objects.count() == 0


def test_a_cce_cannot_type_a_shipping_charge(cce_client, product):
    r = cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 1}], shipping_charge="0", charge="0", grand_total="1", status="delivered", created_by=999), format="json")
    order = Order.objects.get()
    assert r.status_code == 201 and (order.shipping_charge, order.status) == (D("70.00"), "pending") and order.created_by.role == "cce"


def test_the_charge_is_resolved_from_the_address(cce_client, product):
    cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 1}], district="Rajshahi"), format="json")
    order = Order.objects.get()
    assert (order.shipping_zone_name, order.shipping_charge) == ("Outside Dhaka", D("120.00"))


def test_a_guest_customer_needs_no_email_and_no_account(cce_client, product):
    r = cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 1}], email=""), format="json")
    assert r.status_code == 201 and Order.objects.get().customer is None


def test_an_existing_customer_can_be_linked_but_is_never_guessed_from_the_phone(cce_client, customer, product):
    items = [{"product_id": product.id, "quantity": 1}]
    cce_client.post(ORDERS, manual(items, phone=customer.phone), format="json")
    assert Order.objects.get().customer is None  # same phone, but nobody said it's them
    cce_client.post(ORDERS, manual(items, phone=customer.phone, customer_id=customer.id), format="json")
    assert Order.objects.order_by("id").last().customer == customer


def test_customer_id_must_be_an_active_customer(cce_client, admin_user, product):
    items = [{"product_id": product.id, "quantity": 1}]
    assert "customer_id" in details(cce_client.post(ORDERS, manual(items, customer_id=admin_user.id), format="json"))
    assert "customer_id" in details(cce_client.post(ORDERS, manual(items, customer_id=99999), format="json"))


def test_a_manual_order_can_use_a_coupon(cce_client, product):
    CouponFactory(code="SAVE50", amount="50.00")
    cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 2}], coupon="SAVE50"), format="json")
    order = Order.objects.get()
    assert (order.discount_amount, order.grand_total) == (D("50.00"), D("1020.00")) and CouponUsage.objects.get().order_reference == order.number


def test_manual_orders_take_stock_and_reject_overselling(cce_client):
    product = ProductFactory(stock_quantity=2, manage_stock=True)
    assert cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 3}]), format="json").status_code == 400
    assert cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 2}]), format="json").status_code == 201
    product.refresh_from_db()
    assert product.stock_quantity == 0


def test_a_manual_order_can_include_a_variant(cce_client):
    product = ProductFactory(has_variants=True)
    variant = ProductVariantFactory(product=product, stock_quantity=5, regular_price="250.00")
    r = cce_client.post(ORDERS, manual([{"product_id": product.id, "variant_id": variant.id, "quantity": 2}]), format="json")
    item = Order.objects.get().items.get()
    assert r.status_code == 201 and (item.variant, item.unit_price) == (variant, D("250.00"))


def test_the_same_product_listed_twice_is_merged(cce_client, product):
    cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": 1}, {"product_id": product.id, "quantity": 2}]), format="json")
    item = Order.objects.get().items.get()
    assert item.quantity == 3


@pytest.mark.parametrize("items", [[], [{"product_id": 1, "quantity": 0}], [{"product_id": 1, "quantity": 1000}], [{"quantity": 1}], "x"])
def test_bad_item_lists_are_refused(cce_client, items):
    assert cce_client.post(ORDERS, manual(items), format="json").status_code == 400


def test_a_similar_recent_order_only_warns(cce_client, product):
    items = [{"product_id": product.id, "quantity": 1}]
    cce_client.post(ORDERS, manual(items), format="json")
    r = cce_client.post(ORDERS, manual(items), format="json")
    assert r.status_code == 201 and Order.objects.count() == 2
    assert len(r.json()["warnings"]) == 1 and Order.objects.order_by("id").first().number in r.json()["warnings"][0]


def test_no_hourly_cap_or_min_order_for_staff(cce_client, settings, product):
    settings.ORDER_MAX_PER_PHONE_PER_HOUR = 1
    set_site(min_order_amount=D("5000.00"))
    for i in range(3):
        assert cce_client.post(ORDERS, manual([{"product_id": product.id, "quantity": i + 1}]), format="json").status_code == 201


# --- reading: list, filters, search, detail -----------------------------------------------------------------------------------------


@pytest.fixture
def mixed(admin_user, cce_user):
    a = new_order(cce_user, source="facebook", phone="01711111111", name="Amina Khan")
    b = new_order(admin_user, source="call", phone="01722222222", name="Bilal Hossain", district="Sylhet")
    c = new_order(cce_user, source="instagram", phone="01733333333", name="Chaity Rahman")
    services.change_status(c, "confirmed", user=cce_user)
    Order.objects.filter(pk=a.pk).update(created_at=timezone.now() - timedelta(days=10), payment_status="paid")
    return a, b, c


def numbers(response):
    return {o["number"] for o in response.json()["results"]}


def test_list_shape_and_default_ordering(admin_client, mixed):
    body = admin_client.get(ORDERS).json()
    assert body["count"] == 3 and [o["number"] for o in body["results"]] == [mixed[2].number, mixed[1].number, mixed[0].number]
    assert set(body["results"][0]) == {"id", "number", "status", "source", "is_manual", "customer_name", "phone", "district",
                                        "payment_method", "payment_status", "item_count", "grand_total", "shipping_charge", "created_by", "created_at"}


def test_filter_by_source(cce_client, mixed):
    assert numbers(cce_client.get(f"{ORDERS}?source=facebook")) == {mixed[0].number}
    assert numbers(cce_client.get(f"{ORDERS}?source=call")) == {mixed[1].number}
    assert cce_client.get(f"{ORDERS}?source=tiktok").json()["count"] == 0


def test_filter_by_status_payment_status_and_created_by(admin_client, mixed, cce_user, admin_user):
    assert numbers(admin_client.get(f"{ORDERS}?status=confirmed")) == {mixed[2].number}
    assert numbers(admin_client.get(f"{ORDERS}?payment_status=paid")) == {mixed[0].number}
    assert numbers(admin_client.get(f"{ORDERS}?created_by={admin_user.id}")) == {mixed[1].number}
    assert numbers(admin_client.get(f"{ORDERS}?created_by={cce_user.id}")) == {mixed[0].number, mixed[2].number}
    assert numbers(admin_client.get(f"{ORDERS}?is_manual=true")) == {o.number for o in mixed}
    assert numbers(admin_client.get(f"{ORDERS}?district=Sylhet")) == {mixed[1].number}


def test_filter_by_date_range_is_inclusive(admin_client, mixed):
    today = timezone.localdate()
    old = (timezone.now() - timedelta(days=10)).date()
    assert numbers(admin_client.get(f"{ORDERS}?date_from={today}")) == {mixed[1].number, mixed[2].number}
    assert numbers(admin_client.get(f"{ORDERS}?date_to={old}")) == {mixed[0].number}
    assert numbers(admin_client.get(f"{ORDERS}?date_from={old}&date_to={old}")) == {mixed[0].number}
    assert admin_client.get(f"{ORDERS}?date_from={today + timedelta(days=1)}").json()["count"] == 0


def test_search_by_number_phone_and_name(admin_client, mixed):
    assert numbers(admin_client.get(f"{ORDERS}?search={mixed[1].number}")) == {mixed[1].number}
    assert numbers(admin_client.get(f"{ORDERS}?search=01733333333")) == {mixed[2].number}
    assert numbers(admin_client.get(f"{ORDERS}?search=amina")) == {mixed[0].number}


def test_combined_filters_and_ordering(admin_client, mixed):
    assert numbers(admin_client.get(f"{ORDERS}?source=instagram&status=confirmed")) == {mixed[2].number}
    assert admin_client.get(f"{ORDERS}?source=instagram&status=pending").json()["count"] == 0
    assert admin_client.get(f"{ORDERS}?ordering=created_at").json()["results"][0]["number"] == mixed[0].number


def test_soft_deleted_orders_are_hidden(admin_client, admin_user, mixed):
    services.change_status(mixed[1], "cancelled", user=admin_user)
    services.delete_order(mixed[1])
    assert mixed[1].number not in numbers(admin_client.get(ORDERS)) and admin_client.get(url(mixed[1])).status_code == 404


def test_detail_carries_everything_staff_need(cce_client, cce_user, product):
    order = new_order(cce_user, product=product, quantity=2, source="whatsapp", source_note="via Rina's cousin")
    body = cce_client.get(url(order)).json()
    assert body["source"] == "whatsapp" and body["source_note"] == "via Rina's cousin" and body["is_manual"] is True
    assert body["created_by"]["id"] == cce_user.id and body["editable"] is True
    assert body["allowed_transitions"] == ["cancelled", "confirmed", "failed"]
    assert body["history"][0]["changed_by"]["id"] == cce_user.id and body["notes"] == []
    assert body["items"][0]["quantity"] == 2 and body["shipping_zone_name"] == "Inside Dhaka" and body["shipping_overridden"] is False
    assert body["ip_address"] is None and "fingerprint" not in body


def test_the_list_avoids_n_plus_1_queries(admin_client, admin_user, django_assert_max_num_queries):
    for i in range(8):
        new_order(admin_user, phone=f"0171000000{i}")
    with django_assert_max_num_queries(12):
        assert admin_client.get(ORDERS).status_code == 200


# --- status + notes --------------------------------------------------------------------------------------------------------------------


def test_a_cce_changes_status_with_a_note(cce_client, cce_user, order):
    r = cce_client.post(url(order, "status/"), {"status": "confirmed", "note": "customer confirmed by phone"}, format="json")
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert r.json()["allowed_transitions"] == ["cancelled", "failed", "processing"]
    last = r.json()["history"][-1]
    assert (last["from_status"], last["to_status"], last["note"], last["changed_by"]["id"]) == ("pending", "confirmed", "customer confirmed by phone", cce_user.id)


def test_an_invalid_transition_is_a_400_naming_the_status_field(cce_client, order):
    r = cce_client.post(url(order, "status/"), {"status": "delivered"}, format="json")
    assert r.status_code == 400 and "status" in details(r) and Order.objects.get(pk=order.pk).status == "pending"


def test_an_unknown_status_is_a_400(cce_client, order):
    assert cce_client.post(url(order, "status/"), {"status": "teleported"}, format="json").status_code == 400
    assert cce_client.post(url(order, "status/"), {}, format="json").status_code == 400


def test_shipping_with_courier_details(admin_client, admin_user, order):
    Order.objects.filter(pk=order.pk).update(status="processing")
    r = admin_client.post(url(order, "status/"), {"status": "shipped", "courier_name": "Pathao", "tracking_id": "PT-9", "consignment_id": "C-7"}, format="json")
    body = r.json()
    assert (body["status"], body["courier_name"], body["tracking_id"], body["consignment_id"]) == ("shipped", "Pathao", "PT-9", "C-7")


def test_cancelling_through_the_api_restores_stock(cce_client, cce_user):
    product = ProductFactory(stock_quantity=10, manage_stock=True)
    order = new_order(cce_user, product=product, quantity=3)
    assert cce_client.post(url(order, "status/"), {"status": "cancelled"}, format="json").status_code == 200
    product.refresh_from_db()
    assert product.stock_quantity == 10


def test_notes_are_added_listed_and_attributed(cce_client, admin_client, cce_user, order):
    r = cce_client.post(url(order, "notes/"), {"text": "Customer asked for a morning delivery"}, format="json")
    assert r.status_code == 201 and r.json()["author"]["id"] == cce_user.id
    admin_client.post(url(order, "notes/"), {"text": "Approved"}, format="json")
    listed = cce_client.get(url(order, "notes/")).json()
    assert [n["text"] for n in listed] == ["Customer asked for a morning delivery", "Approved"]
    assert OrderNote.objects.filter(order=order).count() == 2
    assert [n["text"] for n in cce_client.get(url(order)).json()["notes"]] == ["Customer asked for a morning delivery", "Approved"]


def test_a_blank_note_is_refused(cce_client, order):
    assert cce_client.post(url(order, "notes/"), {"text": ""}, format="json").status_code == 400
    assert cce_client.post(url(order, "notes/"), {}, format="json").status_code == 400


def test_notes_never_reach_the_customer(cce_client, auth_client, customer):
    order = new_order(customer=customer)
    cce_client.post(url(order, "notes/"), {"text": "risky customer, double check"}, format="json")
    body = auth_client(customer).get(f"/api/v1/orders/{order.number}/").json()
    assert "risky" not in str(body) and "notes" not in body


# --- editing a pending order -------------------------------------------------------------------------------------------------------------


def test_only_pending_orders_can_be_edited(cce_client, admin_user):
    for status in ("confirmed", "processing", "shipped", "delivered", "cancelled"):
        order = new_order(admin_user)
        Order.objects.filter(pk=order.pk).update(status=status)
        r = cce_client.patch(url(order), {"note": "x"}, format="json")
        assert r.status_code == 409 and code(r) == "order_not_editable", status


def test_editing_contact_and_note_leaves_totals_alone(cce_client, order):
    r = cce_client.patch(url(order), {"name": "Rina B.", "email": "rina@example.com", "note": "call first"}, format="json")
    body = r.json()
    assert r.status_code == 200 and (body["customer_name"], body["email"], body["note"]) == ("Rina B.", "rina@example.com", "call first")
    assert (body["subtotal"], body["shipping_charge"], body["grand_total"]) == ("500.00", "70.00", "570.00")
    assert body["history"][-1]["note"].startswith("Order edited") and "customer_name" in body["history"][-1]["note"]


def test_changing_the_address_re_resolves_the_shipping_charge(cce_client, order):
    r = cce_client.patch(url(order), {"district": "Chattogram", "area": "", "address_line": "Agrabad"}, format="json")
    body = r.json()
    assert (body["district"], body["shipping_zone_name"], body["shipping_charge"], body["grand_total"]) == ("Chattogram", "Outside Dhaka", "120.00", "620.00")
    back = cce_client.patch(url(order), {"district": "Dhaka"}, format="json").json()
    assert (back["shipping_zone_name"], back["shipping_charge"], back["grand_total"]) == ("Inside Dhaka", "70.00", "570.00")


def test_the_edit_uses_the_zones_current_charge_not_the_original(cce_client, admin_client, order):
    from apps.shipping.models import DeliveryZone

    zone = DeliveryZone.objects.get(slug="inside-dhaka")
    admin_client.patch(f"/api/v1/admin/shipping/zones/{zone.id}/charge/", {"charge": "90"}, format="json")
    assert Order.objects.get(pk=order.pk).shipping_charge == D("70.00")  # untouched until someone edits
    body = cce_client.patch(url(order), {"note": "x"}, format="json").json()
    assert body["shipping_charge"] == "90.00" and body["grand_total"] == "590.00"


def test_replacing_the_items_recalculates_and_moves_stock_atomically(cce_client, cce_user):
    old = ProductFactory(stock_quantity=10, manage_stock=True, regular_price="500.00")
    new = ProductFactory(stock_quantity=10, manage_stock=True, regular_price="300.00")
    order = new_order(cce_user, product=old, quantity=3)
    r = cce_client.patch(url(order), {"items": [{"product_id": new.id, "quantity": 2}]}, format="json")
    body = r.json()
    assert r.status_code == 200 and [i["product_name"] for i in body["items"]] == [new.name]
    assert (body["subtotal"], body["grand_total"]) == ("600.00", "670.00")
    old.refresh_from_db()
    new.refresh_from_db()
    assert (old.stock_quantity, new.stock_quantity) == (10, 8)  # the old lines went back, the new ones came out
    assert "items" in body["history"][-1]["note"]


def test_editing_items_can_reuse_units_the_order_already_holds(cce_client, cce_user):
    product = ProductFactory(stock_quantity=5, manage_stock=True)
    order = new_order(cce_user, product=product, quantity=5)  # takes everything
    r = cce_client.patch(url(order), {"items": [{"product_id": product.id, "quantity": 4}]}, format="json")
    product.refresh_from_db()
    assert r.status_code == 200 and product.stock_quantity == 1


def test_an_edit_that_cannot_be_satisfied_changes_nothing(cce_client, cce_user):
    have = ProductFactory(stock_quantity=10, manage_stock=True, regular_price="500.00")
    scarce = ProductFactory(stock_quantity=1, manage_stock=True)
    order = new_order(cce_user, product=have, quantity=3)
    r = cce_client.patch(url(order), {"note": "changed", "items": [{"product_id": scarce.id, "quantity": 5}]}, format="json")
    assert r.status_code == 400 and "items" in details(r)
    order.refresh_from_db()
    have.refresh_from_db()
    assert (order.note, order.items.get().product, order.subtotal, have.stock_quantity) == ("", have, D("1500.00"), 7)


def test_the_edit_recomputes_a_kept_coupon_and_the_usage_record(cce_client, cce_user):
    CouponFactory(code="TEN", type="percentage", amount="10.00")
    product = ProductFactory(stock_quantity=20, regular_price="500.00")
    order = new_order(cce_user, product=product, quantity=2, coupon="TEN")
    assert order.discount_amount == D("100.00")
    body = cce_client.patch(url(order), {"items": [{"product_id": product.id, "quantity": 4}]}, format="json").json()
    assert (body["subtotal"], body["discount_amount"], body["grand_total"]) == ("2000.00", "200.00", "1870.00")
    assert CouponUsage.objects.get(order_reference=order.number).discount_amount == D("200.00")


def test_an_edit_that_breaks_the_coupon_says_so_until_it_is_removed(cce_client, cce_user):
    CouponFactory(code="BIG", amount="50.00", min_order_amount="1500.00")
    product = ProductFactory(stock_quantity=20, regular_price="500.00")
    order = new_order(cce_user, product=product, quantity=4, coupon="BIG")
    r = cce_client.patch(url(order), {"items": [{"product_id": product.id, "quantity": 1}]}, format="json")
    assert r.status_code == 400 and "Remove the coupon" in details(r)["items"][0]
    ok = cce_client.patch(url(order), {"items": [{"product_id": product.id, "quantity": 1}], "remove_coupon": True}, format="json")
    body = ok.json()
    assert ok.status_code == 200 and (body["coupon_code"], body["discount_amount"], body["grand_total"]) == ("", "0.00", "570.00")
    assert CouponUsage.objects.count() == 0 and "coupon removed" in body["history"][-1]["note"]


def test_editing_the_phone_updates_the_order(cce_client, order):
    assert cce_client.patch(url(order), {"phone": "01899999999"}, format="json").json()["phone"] == "01899999999"
    assert "phone" in details(cce_client.patch(url(order), {"phone": "123"}, format="json"))


def test_an_empty_items_list_is_refused(cce_client, order):
    assert cce_client.patch(url(order), {"items": []}, format="json").status_code == 400


def test_editing_can_change_the_delivery_method(cce_client, order):
    from apps.shipping.models import DeliveryMethod

    express = DeliveryMethod.objects.get(slug="express")
    express.is_active = True
    express.save()  # save(), not update(): the signal is what refreshes the cached methods
    body = cce_client.patch(url(order), {"delivery_method": "express"}, format="json").json()
    assert (body["delivery_method_name"], body["shipping_charge"]) == ("Express", "170.00")
    assert cce_client.patch(url(order), {"delivery_method": ""}, format="json").json()["shipping_charge"] == "70.00"


def test_an_edit_clears_an_admin_shipping_override(admin_client, cce_client, order):
    admin_client.post(url(order, "shipping-override/"), {"charge": "10", "reason": "VIP"}, format="json")
    body = cce_client.patch(url(order), {"district": "Sylhet"}, format="json").json()
    assert body["shipping_overridden"] is False and body["shipping_charge"] == "120.00" and "override cleared" in body["history"][-1]["note"]


# --- the Admin's shipping override -----------------------------------------------------------------------------------------------------


def test_the_admin_can_override_shipping_with_a_reason(admin_client, admin_user, order):
    r = admin_client.post(url(order, "shipping-override/"), {"charge": "30.00", "reason": "Loyal customer"}, format="json")
    body = r.json()
    assert r.status_code == 200 and (body["shipping_charge"], body["grand_total"]) == ("30.00", "530.00")
    assert body["shipping_overridden"] is True and body["shipping_override_reason"] == "Loyal customer"
    last = body["history"][-1]
    assert last["changed_by"]["id"] == admin_user.id and "70.00 to 30.00" in last["note"] and "Loyal customer" in last["note"]
    assert last["from_status"] == last["to_status"] == "pending"


def test_a_free_override_is_allowed(admin_client, order):
    assert admin_client.post(url(order, "shipping-override/"), {"charge": "0", "reason": "Promo"}, format="json").json()["grand_total"] == "500.00"


def test_the_reason_is_mandatory(admin_client, order):
    for body in ({"charge": "10"}, {"charge": "10", "reason": ""}, {"charge": "10", "reason": "   "}):
        r = admin_client.post(url(order, "shipping-override/"), body, format="json")
        assert r.status_code == 400 and "reason" in details(r), body
    assert Order.objects.get(pk=order.pk).shipping_charge == D("70.00")


@pytest.mark.parametrize("bad", ["-1", "5000.01", "abc", "NaN", ""])
def test_the_override_charge_is_validated_like_a_zone_charge(admin_client, order, bad):
    r = admin_client.post(url(order, "shipping-override/"), {"charge": bad, "reason": "x"}, format="json")
    assert r.status_code == 400 and "charge" in details(r)


@pytest.mark.parametrize("status", ["shipped", "delivered", "cancelled", "returned", "failed"])
def test_the_override_is_locked_once_shipped_or_over(admin_client, admin_user, status):
    order = new_order(admin_user)
    Order.objects.filter(pk=order.pk).update(status=status)
    r = admin_client.post(url(order, "shipping-override/"), {"charge": "1", "reason": "x"}, format="json")
    assert r.status_code == 409 and code(r) == "shipping_locked"


@pytest.mark.parametrize("status", ["confirmed", "processing"])
def test_the_override_works_until_it_ships(admin_client, admin_user, status):
    order = new_order(admin_user)
    Order.objects.filter(pk=order.pk).update(status=status)
    assert admin_client.post(url(order, "shipping-override/"), {"charge": "5", "reason": "x"}, format="json").status_code == 200


# --- deleting, invoice, helpers -------------------------------------------------------------------------------------------------------------------


def test_deleting_a_live_order_is_refused(admin_client, order):
    r = admin_client.delete(url(order))
    assert r.status_code == 409 and code(r) == "order_not_deletable" and Order.objects.filter(pk=order.pk).exists()


def test_the_invoice_has_everything_for_printing(cce_client, admin_user):
    set_site(site_name="GalPal", phone="0255555555", email="hello@galpal.test", address="12 Road, Dhaka", tax_percent=D("5.00"))
    CouponFactory(code="SAVE50", amount="50.00")
    product = ProductFactory(stock_quantity=10, regular_price="500.00", name="Vitamin C Serum")
    order = new_order(admin_user, product=product, quantity=2, coupon="SAVE50", email="rina@example.com", note="ring twice")
    inv = cce_client.get(url(order, "invoice/")).json()
    assert inv["number"] == order.number and inv["currency_symbol"] == "৳" and inv["status"] == "pending"
    assert inv["seller"] == {"name": "GalPal", "phone": "0255555555", "email": "hello@galpal.test", "address": "12 Road, Dhaka"}
    assert inv["bill_to"]["name"] == "Rina Akter" and inv["ship_to"]["address"] == "House 4, Dhaka" and inv["bill_to"]["email"] == "rina@example.com"
    assert inv["items"] == [{"name": "Vitamin C Serum", "sku": product.sku, "variant": "", "quantity": 2, "unit_price": "500.00", "line_total": "1000.00"}]
    assert (inv["subtotal"], inv["discount"], inv["coupon_code"], inv["shipping_zone"], inv["shipping_charge"]) == ("1000.00", "50.00", "SAVE50", "Inside Dhaka", "70.00")
    assert (inv["tax_percent"], inv["tax_amount"], inv["grand_total"]) == ("5.00", "47.50", "1067.50")
    assert (inv["payment_method"], inv["payment_status"], inv["note"]) == ("Cash on delivery", "Unpaid", "ring twice")


def test_the_invoice_survives_the_product_being_deleted(cce_client, admin_user):
    product = ProductFactory(stock_quantity=10, name="Gone Soon")
    order = new_order(admin_user, product=product)
    product.hard_delete()
    assert cce_client.get(url(order, "invoice/")).json()["items"][0]["name"] == "Gone Soon"


def test_the_product_picker_returns_only_what_a_cce_needs(cce_client):
    ProductFactory(name="Vitamin C Serum", sku="SER-1", stock_quantity=7, regular_price="450.00")
    ProductFactory(name="Face Wash", stock_quantity=3)
    ProductFactory(name="Draft Thing", status="draft")
    rows = cce_client.get(f"{ORDERS}helpers/products/?search=serum").json()
    assert len(rows) == 1 and set(rows[0]) == {"product_id", "variant_id", "name", "sku", "variant_label", "price", "stock", "image"}
    assert (rows[0]["name"], rows[0]["sku"], rows[0]["price"], rows[0]["stock"], rows[0]["variant_id"]) == ("Vitamin C Serum", "SER-1", "450.00", 7, None)
    assert rows[0]["image"].startswith("http://testserver/media/")
    names = {r["name"] for r in cce_client.get(f"{ORDERS}helpers/products/").json()}
    assert names == {"Vitamin C Serum", "Face Wash"}  # drafts are not orderable


def test_the_picker_lists_each_active_variant_and_searches_by_variant_sku(cce_client):
    product = ProductFactory(name="Lipstick", has_variants=True)
    ProductVariantFactory(product=product, sku="LIP-ROSE", option_signature="rose", stock_quantity=4, regular_price="300.00")
    ProductVariantFactory(product=product, sku="LIP-RED", option_signature="red", stock_quantity=0, regular_price="320.00")
    ProductVariantFactory(product=product, sku="LIP-OFF", option_signature="off", is_active=False)
    rows = cce_client.get(f"{ORDERS}helpers/products/?search=lipstick").json()
    assert sorted(r["sku"] for r in rows) == ["LIP-RED", "LIP-ROSE"] and all(r["variant_id"] for r in rows)
    by_sku = cce_client.get(f"{ORDERS}helpers/products/?search=LIP-ROSE").json()
    assert [(r["product_id"], r["sku"]) for r in by_sku] == [(product.id, "LIP-ROSE")]  # just that variant


def test_the_picker_is_capped_at_20_products(cce_client):
    for i in range(25):
        ProductFactory(name=f"Bulk {i}")
    assert len(cce_client.get(f"{ORDERS}helpers/products/").json()) == 20


def test_the_shipping_helper_previews_the_charge_read_only(cce_client, order):
    r = cce_client.get(f"{ORDERS}helpers/shipping/?district=Sylhet&subtotal=800")
    assert r.status_code == 200 and (r.json()["charge"], r.json()["zone_name"]) == ("120.00", "Outside Dhaka")
    assert cce_client.get(f"{ORDERS}helpers/shipping/?district=Dhaka&subtotal=800").json()["charge"] == "70.00"
    assert cce_client.post(f"{ORDERS}helpers/shipping/", {}, format="json").status_code == 405
    assert Order.objects.count() == 1


def test_the_shipping_helper_needs_a_district_and_subtotal(cce_client):
    assert cce_client.get(f"{ORDERS}helpers/shipping/?district=Dhaka").status_code == 400
    assert cce_client.get(f"{ORDERS}helpers/shipping/?subtotal=5").status_code == 400
    assert cce_client.get(f"{ORDERS}helpers/shipping/?district=Dhaka&subtotal=-5").status_code == 400


def test_the_customer_lookup_returns_only_name_phone_and_addresses(cce_client):
    customer = UserFactory(phone="01755555555", email="secret@example.com")
    AddressFactory(user=customer, district="Dhaka", is_default=True)
    body = cce_client.get(f"{ORDERS}helpers/customers/?phone=01755555555").json()
    assert set(body) == {"id", "full_name", "phone", "addresses"} and body["id"] == customer.id
    assert body["addresses"][0]["district"] == "Dhaka" and "secret@example.com" not in str(body)
    assert cce_client.get(f"{ORDERS}helpers/customers/?phone=%2B880 1755-555555").status_code == 200  # any phone format


def test_the_customer_lookup_404s_for_unknown_phones_staff_and_inactive_customers(cce_client, admin_user):
    assert cce_client.get(f"{ORDERS}helpers/customers/?phone=01799999999").status_code == 404
    assert cce_client.get(f"{ORDERS}helpers/customers/?phone={admin_user.phone}").status_code == 404  # staff aren't customers
    gone = UserFactory(phone="01766666666", is_active=False)
    assert cce_client.get(f"{ORDERS}helpers/customers/?phone={gone.phone}").status_code == 404
    assert cce_client.get(f"{ORDERS}helpers/customers/").status_code == 400


def test_helper_routes_are_not_mistaken_for_order_ids(cce_client):
    assert cce_client.get(f"{ORDERS}helpers/products/").status_code == 200  # not a 404 from `orders/<pk>/`
