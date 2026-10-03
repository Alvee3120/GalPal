"""Admin discounts — who can manage them, validation, and the single effective price everywhere."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.catalog.filters_product import annotate_effective_price
from apps.catalog.models import Category, Product, ProductCategory, ProductVariant
from apps.catalog.tests.factories import ProductFactory
from apps.discounts import services
from apps.discounts.models import Discount

pytestmark = pytest.mark.django_db

A = "/api/v1/admin/discounts/"


@pytest.fixture(autouse=True)
def _fresh_index():
    services.invalidate()
    yield
    services.invalidate()


def window(start_hours=-1, end_hours=48):
    now = timezone.now()
    return {"starts_at": (now + timedelta(hours=start_hours)).isoformat(), "ends_at": (now + timedelta(hours=end_hours)).isoformat()}


def make(kind="percentage", value="20", target="products", products=(), categories=(), start_hours=-1, end_hours=48, active=True):
    now = timezone.now()
    d = Discount.objects.create(
        name=f"{kind} {value}", kind=kind, value=Decimal(value), target_type=target, is_active=active,
        starts_at=now + timedelta(hours=start_hours), ends_at=now + timedelta(hours=end_hours),
    )
    if products:
        d.products.set(products)
    if categories:
        d.categories.set(categories)
    services.invalidate()
    return d


def product(price="1000.00", **kw):
    return ProductFactory(status="published", regular_price=Decimal(price), discount_price=None, **kw)


def fresh(p):
    return Product.objects.get(pk=p.pk)


# --- access ---------------------------------------------------------------------------------------------------------------


def test_only_admin_manages_discounts(api_client, auth_client, cce_user, customer, admin_user):
    p = product()
    body = {"name": "Sale", "kind": "percentage", "value": "10", "target_type": "products", "product_ids": [p.pk], **window()}
    assert api_client.post(A, body, format="json").status_code == 401
    for user in (cce_user, customer):
        assert auth_client(user).post(A, body, format="json").status_code == 403
        assert auth_client(user).get(A).status_code == 403
    assert auth_client(admin_user).post(A, body, format="json").status_code == 201


# --- validation -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("override", [
    {"value": "0"}, {"value": "101"}, {"product_ids": []},
    {"kind": "fixed", "value": "5000"},  # more than the product's price
])
def test_invalid_discounts_are_rejected(auth_client, admin_user, override):
    p = product("1000.00")
    body = {"name": "Sale", "kind": "percentage", "value": "10", "target_type": "products", "product_ids": [p.pk], **window(), **override}
    assert auth_client(admin_user).post(A, body, format="json").status_code == 400


def test_end_must_be_after_start_and_category_must_be_given(auth_client, admin_user):
    w = window()
    client = auth_client(admin_user)
    assert client.post(A, {"name": "x", "kind": "percentage", "value": "10", "target_type": "category",
                           "starts_at": w["ends_at"], "ends_at": w["starts_at"], "category_ids": [Category.objects.create(name="C", slug="c").pk]},
                       format="json").status_code == 400
    assert client.post(A, {"name": "x", "kind": "percentage", "value": "10", "target_type": "category", **w}, format="json").status_code == 400


# --- pricing ---------------------------------------------------------------------------------------------------------------


def test_percentage_and_fixed_prices():
    p = product("2000.00")
    make(products=[p], value="20")
    assert fresh(p).effective_price == Decimal("1600.00") and fresh(p).discount_percentage == 20
    Discount.objects.all().delete()
    make(kind="fixed", value="300", products=[p])
    assert fresh(p).effective_price == Decimal("1700.00") and fresh(p).applied_discount["type"] == "fixed"


def test_regular_price_is_never_changed_and_returns_after_expiry():
    p = product("2000.00")
    d = make(products=[p], value="20")
    assert fresh(p).regular_price == Decimal("2000.00")
    Discount.objects.filter(pk=d.pk).update(ends_at=timezone.now() - timedelta(minutes=1))
    services.invalidate()
    assert fresh(p).effective_price == Decimal("2000.00") and not fresh(p).on_sale


def test_scheduled_and_inactive_discounts_do_not_apply():
    p = product("1000.00")
    make(products=[p], value="50", start_hours=2)
    make(products=[p], value="40", active=False)
    assert fresh(p).effective_price == Decimal("1000.00")


def test_category_discount_includes_sub_categories_only():
    parent = Category.objects.create(name="Skincare", slug="skincare")
    child = Category.objects.create(name="Serums", slug="serums", parent=parent)
    inside, outside = product("1000.00"), product("1000.00")
    ProductCategory.objects.create(product=inside, category=child, is_primary=True)
    make(target="category", categories=[parent], value="10")
    assert fresh(inside).effective_price == Decimal("900.00")
    assert fresh(outside).effective_price == Decimal("1000.00")


def test_product_discount_beats_category_and_own_sale_competes_without_stacking():
    cat = Category.objects.create(name="Lips", slug="lips")
    p = product("1000.00")
    ProductCategory.objects.create(product=p, category=cat, is_primary=True)
    make(target="category", categories=[cat], value="50")  # 500
    make(products=[p], value="10")  # 900 — product-specific wins even though the category one is cheaper
    assert fresh(p).effective_price == Decimal("900.00") and fresh(p).applied_discount["value"] == Decimal("10.00")
    Product.objects.filter(pk=p.pk).update(discount_price=Decimal("850.00"))
    assert fresh(p).effective_price == Decimal("850.00") and fresh(p).applied_discount is None  # the lower one, not both


def test_variants_are_discounted_on_their_own_price():
    p = product("1000.00", has_variants=True)
    v = ProductVariant.objects.create(product=p, sku="V-1", regular_price=Decimal("1200.00"), stock_quantity=5)
    make(products=[p], value="25")
    assert ProductVariant.objects.get(pk=v.pk).effective_price == Decimal("900.00")


def test_sql_price_matches_python_price():
    p = product("1000.00")
    make(products=[p], kind="fixed", value="150")
    row = annotate_effective_price(Product.objects.filter(pk=p.pk)).values("effective_price_db", "on_sale_db").get()
    assert row["effective_price_db"] == fresh(p).effective_price == Decimal("850.00") and row["on_sale_db"] is True


def test_status_filters(auth_client, admin_user):
    p = product()
    make(products=[p])
    make(products=[p], start_hours=5)
    make(products=[p], start_hours=-48, end_hours=-1)
    make(products=[p], active=False)
    client = auth_client(admin_user)
    for status in ("active", "scheduled", "expired", "inactive"):
        body = client.get(f"{A}?status={status}").json()
        assert body["count"] == 1 and body["results"][0]["status"] == status


def test_a_discount_can_cover_several_categories():
    face, lips, other = (Category.objects.create(name=n, slug=n.lower()) for n in ("Face", "Lips", "Hair"))
    a, b, c = product("1000.00"), product("1000.00"), product("1000.00")
    for prod, cat in ((a, face), (b, lips), (c, other)):
        ProductCategory.objects.create(product=prod, category=cat, is_primary=True)
    make(target="category", categories=[face, lips], value="10")
    assert fresh(a).effective_price == fresh(b).effective_price == Decimal("900.00")
    assert fresh(c).effective_price == Decimal("1000.00")


def test_category_discount_needs_at_least_one_category(auth_client, admin_user):
    body = {"name": "x", "kind": "percentage", "value": "10", "target_type": "category", "category_ids": [], **window()}
    assert auth_client(admin_user).post(A, body, format="json").status_code == 400
