"""
Django admin "add / change product" form: the category picker (the ProductCategory inline).
These post the real admin forms, so they cover the formset, the primary-category rule and the
database's one-primary-per-product index together.
"""
import pytest
from django.urls import reverse

from apps.catalog.models import Product, ProductCategory

from .factories import CategoryFactory, ProductFactory, make_image

pytestmark = pytest.mark.django_db

ADD = reverse("admin:catalog_product_add")


@pytest.fixture
def staff_client(client, admin_user):
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.save()
    client.force_login(admin_user)
    return client


def management_data(response):
    """TOTAL/INITIAL/MIN/MAX_FORMS for every inline, straight from the rendered page."""
    data = {}
    for inline in response.context["inline_admin_formsets"]:
        management = inline.formset.management_form
        prefix = inline.formset.prefix
        data[f"{prefix}-TOTAL_FORMS"] = "0"
        data[f"{prefix}-INITIAL_FORMS"] = management.initial.get("INITIAL_FORMS", 0)
        data[f"{prefix}-MIN_NUM_FORMS"] = "0"
        data[f"{prefix}-MAX_NUM_FORMS"] = "1000"
    return data


def product_post(response, *, name="Glow Serum", sku="ADM-1", categories=(), **extra):
    """categories: [(category, is_primary), ...] -> the inline formset's rows."""
    data = management_data(response)
    data.update({
        "name": name, "slug": sku.lower(), "sku": sku, "regular_price": "500.00", "status": "published",
        "stock_status": "in_stock", "manage_stock": "on", "low_stock_threshold": "5", "stock_quantity": "3",
        "feature_image": make_image(),
    })
    rows = list(categories)
    prefix = "category_links"
    data[f"{prefix}-TOTAL_FORMS"] = str(len(rows))
    for i, (category, primary) in enumerate(rows):
        data[f"{prefix}-{i}-category"] = category.pk
        if primary:
            data[f"{prefix}-{i}-is_primary"] = "on"
    data.update(extra)
    return data


def links(product):
    return {link.category_id: link.is_primary for link in ProductCategory.objects.filter(product=product)}


def create(staff_client, **kwargs):
    page = staff_client.get(ADD)
    assert page.status_code == 200
    return staff_client.post(ADD, product_post(page, **kwargs))


def test_the_add_form_has_a_category_picker(staff_client):
    page = staff_client.get(ADD)
    assert "category_links" in {inline.formset.prefix for inline in page.context["inline_admin_formsets"]}
    html = page.content.decode()
    assert "Categories (tick" in html and "category_links-0-category" in html


def test_create_a_product_with_categories_and_a_primary(staff_client):
    a, b = CategoryFactory(), CategoryFactory()
    r = create(staff_client, categories=[(a, False), (b, True)])
    assert r.status_code == 302, r.context["errors"] if r.context else r.content[:300]
    assert links(Product.objects.get(sku="ADM-1")) == {a.pk: False, b.pk: True}


def test_the_first_category_becomes_primary_when_none_is_ticked(staff_client):
    a, b = CategoryFactory(), CategoryFactory()
    assert create(staff_client, categories=[(a, False), (b, False)]).status_code == 302
    assert links(Product.objects.get(sku="ADM-1")) == {a.pk: True, b.pk: False}


def test_a_single_category_is_primary(staff_client):
    a = CategoryFactory()
    assert create(staff_client, categories=[(a, False)]).status_code == 302
    assert links(Product.objects.get(sku="ADM-1")) == {a.pk: True}


def test_a_product_without_categories_is_still_allowed(staff_client):
    assert create(staff_client).status_code == 302
    assert links(Product.objects.get(sku="ADM-1")) == {}


def test_two_primaries_are_rejected_with_a_form_error_not_a_500(staff_client):
    a, b = CategoryFactory(), CategoryFactory()
    r = create(staff_client, categories=[(a, True), (b, True)])
    assert r.status_code == 200 and b"Only one category can be the primary" in r.content
    assert not Product.objects.filter(sku="ADM-1").exists()


def test_the_same_category_twice_is_rejected(staff_client):
    a = CategoryFactory()
    r = create(staff_client, categories=[(a, True), (a, False)])
    assert r.status_code == 200 and not Product.objects.filter(sku="ADM-1").exists()


# --- editing ---------------------------------------------------------------------------------------


def change_url(product):
    return reverse("admin:catalog_product_change", args=[product.pk])


def edit_post(staff_client, product, rows, **extra):
    """rows: [(link_or_None, category, primary, delete)] -> the change form's category rows."""
    page = staff_client.get(change_url(product))
    data = product_post(page, name=product.name, sku=product.sku)
    data.pop("feature_image")  # keep the existing image
    prefix = "category_links"
    existing = [row for row in rows if row[0] is not None]
    data[f"{prefix}-TOTAL_FORMS"] = str(len(rows))
    data[f"{prefix}-INITIAL_FORMS"] = str(len(existing))
    for i, (link, category, primary, delete) in enumerate(rows):
        for key in ("category", "is_primary", "id", "product", "DELETE"):
            data.pop(f"{prefix}-{i}-{key}", None)
        data[f"{prefix}-{i}-category"] = category.pk
        data[f"{prefix}-{i}-product"] = product.pk
        if link is not None:
            data[f"{prefix}-{i}-id"] = link.pk
        if primary:
            data[f"{prefix}-{i}-is_primary"] = "on"
        if delete:
            data[f"{prefix}-{i}-DELETE"] = "on"
    data.update(extra)
    return staff_client.post(change_url(product), data)


@pytest.fixture
def product_with_two():
    product = ProductFactory()
    a, b = CategoryFactory(), CategoryFactory()
    la = ProductCategory.objects.create(product=product, category=a, is_primary=True)
    lb = ProductCategory.objects.create(product=product, category=b, is_primary=False)
    return product, (la, a), (lb, b)


def test_switching_the_primary_between_existing_rows_does_not_crash(staff_client, product_with_two):
    product, (la, a), (lb, b) = product_with_two
    r = edit_post(staff_client, product, [(la, a, False, False), (lb, b, True, False)])
    assert r.status_code == 302
    assert links(product) == {a.pk: False, b.pk: True}


def test_saving_without_touching_categories_keeps_the_primary(staff_client, product_with_two):
    product, (la, a), (lb, b) = product_with_two
    assert edit_post(staff_client, product, [(la, a, True, False), (lb, b, False, False)]).status_code == 302
    assert links(product) == {a.pk: True, b.pk: False}


def test_removing_the_primary_promotes_a_remaining_category(staff_client, product_with_two):
    product, (la, a), (lb, b) = product_with_two
    r = edit_post(staff_client, product, [(la, a, True, True), (lb, b, False, False)])
    assert r.status_code == 302
    assert links(product) == {b.pk: True}


def test_removing_the_primary_while_ticking_another_in_the_same_save(staff_client, product_with_two):
    product, (la, a), (lb, b) = product_with_two
    r = edit_post(staff_client, product, [(la, a, True, True), (lb, b, True, False)])
    assert r.status_code == 302
    assert links(product) == {b.pk: True}


def test_adding_a_category_to_an_existing_product(staff_client, product_with_two):
    product, (la, a), (lb, b) = product_with_two
    c = CategoryFactory()
    r = edit_post(staff_client, product, [(la, a, True, False), (lb, b, False, False), (None, c, False, False)])
    assert r.status_code == 302
    assert links(product) == {a.pk: True, b.pk: False, c.pk: False}


def test_deleting_every_category_leaves_none(staff_client, product_with_two):
    product, (la, a), (lb, b) = product_with_two
    assert edit_post(staff_client, product, [(la, a, True, True), (lb, b, False, True)]).status_code == 302
    assert links(product) == {}


def test_switching_the_primary_when_the_new_primary_row_is_saved_first(staff_client, product_with_two):
    """Row order matters to the save loop: the new primary is written while the old one still holds the flag."""
    product, (la, a), (lb, b) = product_with_two
    r = edit_post(staff_client, product, [(lb, b, True, False), (la, a, False, False)])
    assert r.status_code == 302
    assert links(product) == {a.pk: False, b.pk: True}


def test_removing_the_primary_and_ticking_another_listed_before_it(staff_client, product_with_two):
    product, (la, a), (lb, b) = product_with_two
    r = edit_post(staff_client, product, [(lb, b, True, False), (la, a, True, True)])
    assert r.status_code == 302
    assert links(product) == {b.pk: True}
