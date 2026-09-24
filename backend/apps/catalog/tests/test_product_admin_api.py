import io

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.catalog.models import Product, ProductAttribute, ProductVariant, StockMovement

from .factories import (
    AttributeValueFactory,
    BrandFactory,
    CategoryFactory,
    ProductAttributeFactory,
    ProductFactory,
    ProductImageFactory,
    ProductVariantFactory,
    TagFactory,
    make_image,
)

pytestmark = pytest.mark.django_db

PRODUCTS = "/api/v1/admin/products/"
ATTRIBUTES = "/api/v1/admin/product-attributes/"
VALUES = "/api/v1/admin/attribute-values/"
STOCK = "/api/v1/admin/stock/adjust/"
MOVEMENTS = "/api/v1/admin/stock-movements/"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


def png(name="a.png", fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "pink").save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue())


def details(response):
    return response.json()["error"]["details"]


def minimal_payload(**overrides):
    payload = {"name": "Vitamin C Serum", "sku": "VCS-001", "regular_price": "1200.00", "feature_image": png()}
    payload.update(overrides)
    return payload


# --- access control -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url", [PRODUCTS, ATTRIBUTES, VALUES, STOCK, MOVEMENTS]
)
def test_anonymous_and_customer_are_locked_out(api_client, auth_client, customer, url):
    assert api_client.get(url if url != STOCK else STOCK).status_code == 401
    assert auth_client(customer).get(url).status_code in (403, 405)


def test_cce_manages_products_but_not_bulk_or_duplicate(auth_client, cce_user):
    product = ProductFactory()
    client = auth_client(cce_user)
    assert client.get(PRODUCTS).status_code == 200
    assert client.get(f"{PRODUCTS}{product.id}/").status_code == 200
    assert client.post(PRODUCTS, minimal_payload(), format="multipart").status_code == 201
    assert client.patch(f"{PRODUCTS}{product.id}/", {"name": "x"}, format="json").status_code == 200
    assert client.post(f"{PRODUCTS}{product.id}/duplicate/").status_code == 403
    assert client.post(f"{PRODUCTS}bulk/activate/", {"product_ids": [product.id]}, format="json").status_code == 403
    assert client.post(f"{PRODUCTS}bulk/stock/", {"items": []}, format="json").status_code == 403
    assert client.get(MOVEMENTS).status_code == 403
    assert client.post(ATTRIBUTES, {"name": "Colour"}, format="json").status_code == 403
    assert client.delete(f"{PRODUCTS}{product.id}/").status_code == 204


def test_cce_can_add_an_attribute_value_but_not_edit_one(auth_client, cce_user):
    size = ProductAttributeFactory(name="Size")
    client = auth_client(cce_user)
    r = client.post(VALUES, {"attribute": size.id, "value": "75ml"}, format="json")
    assert r.status_code == 201
    assert client.post(VALUES, {"attribute": size.id, "value": "75ML"}, format="json").status_code == 400  # no duplicates
    assert client.patch(f"{VALUES}{r.json()['id']}/", {"value": "80ml"}, format="json").status_code == 403
    assert client.delete(f"{VALUES}{r.json()['id']}/").status_code == 403


def test_cce_stock_adjustments_are_logged_as_them(auth_client, cce_user):
    product = ProductFactory(stock_quantity=0, manage_stock=True)
    r = auth_client(cce_user).post(STOCK, {"product_id": product.id, "quantity_change": 7, "reason": "manual"}, format="json")
    assert r.status_code == 200
    product.refresh_from_db()
    assert product.stock_quantity == 7 and StockMovement.objects.get(product=product).user == cce_user


def test_stock_status_follows_the_quantity_unless_backorder(admin_client):
    product = ProductFactory(stock_quantity=0, manage_stock=True, stock_status="out_of_stock")
    url = f"{PRODUCTS}{product.id}/"
    assert admin_client.patch(url, {"stock_status": "in_stock"}, format="json").json()["stock_status"] == "out_of_stock"
    assert admin_client.patch(url, {"stock_status": "backorder"}, format="json").json()["stock_status"] == "backorder"


def test_a_sale_cannot_end_before_it_starts(admin_client):
    product = ProductFactory()
    r = admin_client.patch(
        f"{PRODUCTS}{product.id}/", {"sale_start_at": "2026-10-10T10:00", "sale_end_at": "2026-10-09T10:00"}, format="json"
    )
    assert r.status_code == 400 and "sale_end_at" in r.json()["error"]["details"]


def test_sending_no_categories_clears_them(admin_client):
    category = CategoryFactory()
    product = ProductFactory()
    url = f"{PRODUCTS}{product.id}/"
    admin_client.patch(url, {"category_ids": [category.id]}, format="json")
    assert admin_client.patch(url, {"category_ids": [], "primary_category_id": None}, format="json").json()["categories"] == []


def test_the_list_summarises_variant_stock(admin_client):
    product = ProductFactory(has_variants=True, stock_quantity=0)
    product.variants.create(sku="V-A", stock_quantity=4, option_signature="a")
    product.variants.create(sku="V-B", stock_quantity=6, option_signature="b")
    product.variants.create(sku="V-C", stock_quantity=9, is_active=False, option_signature="c")
    row = admin_client.get(PRODUCTS).json()["results"][0]
    assert row["variant_stock"] == {"count": 3, "active_count": 2, "stock_quantity": 10, "untracked_count": 0}


# --- create ----------------------------------------------------------------------------------------


def test_create_minimal_product(admin_client):
    r = admin_client.post(PRODUCTS, minimal_payload(), format="multipart")
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "vitamin-c-serum" and body["status"] == "draft" and body["stock_quantity"] == 0
    assert body["feature_image"].startswith("http://testserver/media/products/")
    assert body["effective_price"] == "1200.00" and body["categories"] == [] and body["variants"] == []


def test_feature_image_is_required_on_create(admin_client):
    payload = minimal_payload()
    del payload["feature_image"]
    r = admin_client.post(PRODUCTS, payload, format="multipart")
    assert r.status_code == 400 and "feature_image" in details(r)


def test_sku_must_be_unique_across_products_and_variants(admin_client):
    ProductFactory(sku="TAKEN")
    r = admin_client.post(PRODUCTS, minimal_payload(sku="TAKEN"), format="multipart")
    assert r.status_code == 400 and "sku" in details(r)
    ProductVariantFactory(sku="TAKEN-V")
    r = admin_client.post(PRODUCTS, minimal_payload(sku="TAKEN-V"), format="multipart")
    assert r.status_code == 400 and "sku" in details(r)


def test_discount_price_must_be_lower_than_regular(admin_client):
    r = admin_client.post(PRODUCTS, minimal_payload(regular_price="100.00", discount_price="150.00"), format="multipart")
    assert r.status_code == 400 and "discount_price" in details(r)
    r = admin_client.post(PRODUCTS, minimal_payload(regular_price="100.00", discount_price="100.00"), format="multipart")
    assert r.status_code == 400 and "discount_price" in details(r)


def test_create_with_categories_and_primary(admin_client):
    a, b = CategoryFactory(), CategoryFactory()
    r = admin_client.post(PRODUCTS, minimal_payload(category_ids=[a.id, b.id], primary_category_id=b.id), format="multipart")
    assert r.status_code == 201
    body = r.json()
    by_id = {c["id"]: c["is_primary"] for c in body["categories"]}
    assert by_id == {a.id: False, b.id: True}


def test_create_with_categories_defaults_primary_to_first(admin_client):
    a, b = CategoryFactory(), CategoryFactory()
    r = admin_client.post(PRODUCTS, minimal_payload(category_ids=[a.id, b.id]), format="multipart")
    by_id = {c["id"]: c["is_primary"] for c in r.json()["categories"]}
    assert by_id[a.id] is True


def test_create_with_unknown_category_is_400(admin_client):
    r = admin_client.post(PRODUCTS, minimal_payload(category_ids=[999999]), format="multipart")
    assert r.status_code == 400 and "category_ids" in details(r)


def test_create_with_tags(admin_client):
    tag = TagFactory()
    r = admin_client.post(PRODUCTS, minimal_payload(tag_ids=[tag.id]), format="multipart")
    assert r.json()["tags"][0]["id"] == tag.id


def test_create_full_cosmetics_fields(admin_client):
    brand = BrandFactory()
    payload = minimal_payload(
        brand=brand.id, short_description="Brightens skin", full_description="<p>Full</p>",
        user_guide="<p>Apply nightly</p>", skin_type=["oily", "dry"], key_ingredients=["Vitamin C", "Hyaluronic Acid"],
        ingredients="Aqua, Ascorbic Acid", size_value="30.00", size_unit="ml", country_of_origin="South Korea",
        manufacture_date="2025-01-01", expiry_date="2027-01-01", gender="women",
        is_featured=True, is_new_arrival=True, meta_title="Buy Vitamin C Serum",
    )
    r = admin_client.post(PRODUCTS, payload, format="multipart")
    assert r.status_code == 201
    body = r.json()
    assert body["brand"] == brand.id and set(body["skin_type"]) == {"oily", "dry"}
    assert body["key_ingredients"] == ["Vitamin C", "Hyaluronic Acid"]
    assert body["size_value"] == "30.00" and body["size_unit"] == "ml" and body["gender"] == "women"
    assert body["is_featured"] is True and body["meta_title"] == "Buy Vitamin C Serum"


def test_stock_quantity_cannot_be_set_directly(admin_client):
    r = admin_client.post(PRODUCTS, minimal_payload(stock_quantity=50), format="multipart")
    assert r.status_code == 201 and r.json()["stock_quantity"] == 0


# --- read / list -------------------------------------------------------------------------------------


def test_list_uses_compact_shape_and_includes_all_statuses(admin_client):
    ProductFactory(status="draft")
    ProductFactory(status="archived")
    body = admin_client.get(PRODUCTS).json()
    assert body["count"] == 2
    assert set(body["results"][0]) == {
        "id", "name", "slug", "feature_image", "brand", "sku", "regular_price", "discount_price",
        "effective_price", "stock_quantity", "manage_stock", "stock_status", "in_stock", "is_low_stock", "status",
        "is_featured", "is_new_arrival", "is_bestseller", "has_variants", "variant_stock", "average_rating", "review_count",
        "created_at", "updated_at",
    }


def test_soft_deleted_products_are_excluded_from_admin_list(admin_client):
    product = ProductFactory()
    product.delete()
    assert admin_client.get(PRODUCTS).json()["count"] == 0
    assert admin_client.get(f"{PRODUCTS}{product.id}/").status_code == 404


def test_filters_status_flags_brand_category(admin_client):
    brand = BrandFactory()
    category = CategoryFactory()
    a = ProductFactory(status="draft", brand=brand, is_featured=True)
    from apps.catalog import services

    services.set_categories(a, [category.id])
    ProductFactory(status="published")
    client = admin_client
    ids = lambda qs: {p["id"] for p in client.get(f"{PRODUCTS}?{qs}").json()["results"]}  # noqa: E731
    assert ids("status=draft") == {a.id}
    assert ids("is_featured=true") == {a.id}
    assert ids(f"brand={brand.id}") == {a.id}
    assert ids(f"category={category.id}") == {a.id}


def test_search_and_ordering(admin_client):
    ProductFactory(name="Zeta", regular_price="10.00")
    ProductFactory(name="Alpha", regular_price="90.00")
    assert [p["name"] for p in admin_client.get(f"{PRODUCTS}?ordering=name").json()["results"]] == ["Alpha", "Zeta"]
    assert [p["name"] for p in admin_client.get(f"{PRODUCTS}?search=zeta").json()["results"]] == ["Zeta"]


# --- update ------------------------------------------------------------------------------------------


def test_patch_updates_scalar_fields(admin_client):
    product = ProductFactory(name="Old")
    r = admin_client.patch(f"{PRODUCTS}{product.id}/", {"name": "New", "is_bestseller": True}, format="json")
    assert r.status_code == 200 and r.json()["name"] == "New" and r.json()["is_bestseller"] is True


def test_patch_replaces_categories_and_can_change_primary(admin_client):
    product = ProductFactory()
    a, b = CategoryFactory(), CategoryFactory()
    admin_client.patch(f"{PRODUCTS}{product.id}/", {"category_ids": [a.id, b.id], "primary_category_id": a.id}, format="json")
    r = admin_client.patch(f"{PRODUCTS}{product.id}/", {"primary_category_id": b.id}, format="json")
    by_id = {c["id"]: c["is_primary"] for c in r.json()["categories"]}
    assert by_id == {a.id: False, b.id: True}


def test_patch_replacing_feature_image_deletes_the_old_file(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        product_id = admin_client.post(PRODUCTS, minimal_payload(), format="multipart").json()["id"]
    old_name = Product.objects.get(pk=product_id).feature_image.name
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.patch(f"{PRODUCTS}{product_id}/", {"feature_image": png("two.png")}, format="multipart")
    new_name = Product.objects.get(pk=product_id).feature_image.name
    assert new_name != old_name and default_storage.exists(new_name) and not default_storage.exists(old_name)


def test_patch_sku_uniqueness_ignores_self(admin_client):
    product = ProductFactory(sku="MINE")
    assert admin_client.patch(f"{PRODUCTS}{product.id}/", {"sku": "MINE"}, format="json").status_code == 200
    other = ProductFactory(sku="OTHER")
    assert "sku" in details(admin_client.patch(f"{PRODUCTS}{other.id}/", {"sku": "MINE"}, format="json"))


def test_delete_is_a_soft_delete(admin_client):
    product = ProductFactory()
    assert admin_client.delete(f"{PRODUCTS}{product.id}/").status_code == 204
    assert Product.all_objects.get(pk=product.pk).is_deleted


# --- images (nested) ---------------------------------------------------------------------------------


def test_add_list_update_and_delete_gallery_image(admin_client, django_capture_on_commit_callbacks):
    product = ProductFactory()
    url = f"{PRODUCTS}{product.id}/images/"
    r = admin_client.post(url, {"image": png("g.png"), "alt_text": "Front", "sort_order": 1}, format="multipart")
    assert r.status_code == 201
    image_id = r.json()["id"]
    body = admin_client.get(url).json()
    assert body["count"] == 1 and body["results"][0]["alt_text"] == "Front"
    assert admin_client.patch(f"{url}{image_id}/", {"alt_text": "Updated"}, format="json").json()["alt_text"] == "Updated"
    name = Product.objects.get(pk=product.id).images.get().image.name
    with django_capture_on_commit_callbacks(execute=True):
        assert admin_client.delete(f"{url}{image_id}/").status_code == 204
    assert not default_storage.exists(name)


def test_image_reorder(admin_client):
    product = ProductFactory()
    a = ProductImageFactory(product=product, sort_order=0)
    b = ProductImageFactory(product=product, sort_order=1)
    url = f"{PRODUCTS}{product.id}/images/reorder/"
    r = admin_client.post(url, [b.id, a.id], format="json")
    assert r.status_code == 200
    a.refresh_from_db(); b.refresh_from_db()
    assert (b.sort_order, a.sort_order) == (0, 1)


def test_image_reorder_rejects_a_mismatched_id_set(admin_client):
    product = ProductFactory()
    ProductImageFactory(product=product)
    url = f"{PRODUCTS}{product.id}/images/reorder/"
    assert admin_client.post(url, [999999], format="json").status_code == 400


def test_images_are_scoped_to_their_product(admin_client):
    a, b = ProductFactory(), ProductFactory()
    image = ProductImageFactory(product=a)
    assert admin_client.get(f"{PRODUCTS}{b.id}/images/{image.id}/").status_code == 404


def test_invalid_gallery_image_is_rejected(admin_client):
    product = ProductFactory()
    bad = SimpleUploadedFile("x.png", b"<html>nope</html>")
    r = admin_client.post(f"{PRODUCTS}{product.id}/images/", {"image": bad}, format="multipart")
    assert r.status_code == 400


# --- variants (nested) -------------------------------------------------------------------------------


def test_add_variant_with_attribute_values(admin_client):
    product = ProductFactory()
    attribute = ProductAttributeFactory(name="Shade")
    rose = AttributeValueFactory(attribute=attribute, value="Rose")
    url = f"{PRODUCTS}{product.id}/variants/"
    r = admin_client.post(url, {"sku": "VAR-1", "attribute_value_ids": [rose.id], "regular_price": "500.00"}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["attribute_values"][0]["value"] == "Rose" and body["regular_price"] == "500.00"


def test_variant_sku_must_be_globally_unique(admin_client):
    ProductFactory(sku="CLASH")
    product = ProductFactory()
    r = admin_client.post(f"{PRODUCTS}{product.id}/variants/", {"sku": "CLASH", "attribute_value_ids": []}, format="json")
    assert r.status_code == 400 and "sku" in details(r)


def test_variant_discount_price_must_be_lower(admin_client):
    product = ProductFactory()
    r = admin_client.post(
        f"{PRODUCTS}{product.id}/variants/",
        {"sku": "V1", "attribute_value_ids": [], "regular_price": "50.00", "discount_price": "80.00"}, format="json",
    )
    assert r.status_code == 400 and "discount_price" in details(r)


def test_duplicate_option_combination_is_rejected(admin_client):
    product = ProductFactory()
    value = AttributeValueFactory()
    admin_client.post(f"{PRODUCTS}{product.id}/variants/", {"sku": "V1", "attribute_value_ids": [value.id]}, format="json")
    r = admin_client.post(f"{PRODUCTS}{product.id}/variants/", {"sku": "V2", "attribute_value_ids": [value.id]}, format="json")
    assert r.status_code == 400 and "attribute_values" in details(r)


def test_update_and_delete_variant(admin_client, django_capture_on_commit_callbacks):
    variant = ProductVariantFactory()
    url = f"{PRODUCTS}{variant.product_id}/variants/{variant.id}/"
    assert admin_client.patch(url, {"is_active": False}, format="json").json()["is_active"] is False
    with django_capture_on_commit_callbacks(execute=True):
        assert admin_client.delete(url).status_code == 204
    assert not ProductVariant.objects.filter(pk=variant.pk).exists()


def test_variant_stock_is_read_only_on_the_nested_endpoint(admin_client):
    product = ProductFactory()
    r = admin_client.post(f"{PRODUCTS}{product.id}/variants/", {"sku": "V1", "attribute_value_ids": [], "stock_quantity": 99}, format="json")
    assert r.json()["stock_quantity"] == 0


# --- stock -------------------------------------------------------------------------------------------


def test_single_stock_adjustment(admin_client):
    product = ProductFactory(stock_quantity=0)
    r = admin_client.post(STOCK, {"product_id": product.id, "quantity_change": 20, "reason": "restock"}, format="json")
    assert r.status_code == 200 and r.json()["balance_after"] == 20
    product.refresh_from_db()
    assert product.stock_quantity == 20


def test_stock_adjustment_requires_exactly_one_target(admin_client):
    r = admin_client.post(STOCK, {"quantity_change": 1, "reason": "restock"}, format="json")
    assert r.status_code == 400
    product = ProductFactory()
    variant = ProductVariantFactory()
    r = admin_client.post(STOCK, {"product_id": product.id, "variant_id": variant.id, "quantity_change": 1, "reason": "restock"}, format="json")
    assert r.status_code == 400


def test_stock_adjustment_rejects_negative_below_zero(admin_client):
    product = ProductFactory(stock_quantity=2)
    r = admin_client.post(STOCK, {"product_id": product.id, "quantity_change": -5, "reason": "sale"}, format="json")
    assert r.status_code == 400 and "quantity_change" in details(r)


def test_stock_adjustment_unknown_product_is_400(admin_client):
    r = admin_client.post(STOCK, {"product_id": 999999, "quantity_change": 1, "reason": "restock"}, format="json")
    assert r.status_code == 400 and "product_id" in details(r)


def test_bulk_stock_update_is_all_or_nothing(admin_client):
    a = ProductFactory(stock_quantity=10)
    b = ProductFactory(stock_quantity=1)
    payload = {"items": [
        {"product_id": a.id, "quantity_change": -5, "reason": "sale"},
        {"product_id": b.id, "quantity_change": -5, "reason": "sale"},  # would go negative
    ]}
    r = admin_client.post(f"{PRODUCTS}bulk/stock/", payload, format="json")
    assert r.status_code == 400
    a.refresh_from_db(); b.refresh_from_db()
    assert a.stock_quantity == 10 and b.stock_quantity == 1  # nothing applied


def test_bulk_stock_update_success(admin_client):
    a, b = ProductFactory(stock_quantity=10), ProductFactory(stock_quantity=10)
    payload = {"items": [
        {"product_id": a.id, "quantity_change": -3, "reason": "sale"},
        {"product_id": b.id, "quantity_change": 7, "reason": "restock"},
    ]}
    r = admin_client.post(f"{PRODUCTS}bulk/stock/", payload, format="json")
    assert r.status_code == 200 and len(r.json()) == 2
    a.refresh_from_db(); b.refresh_from_db()
    assert a.stock_quantity == 7 and b.stock_quantity == 17


def test_global_inventory_log_is_filterable(admin_client):
    product = ProductFactory(stock_quantity=0)
    admin_client.post(STOCK, {"product_id": product.id, "quantity_change": 5, "reason": "restock"}, format="json")
    admin_client.post(STOCK, {"product_id": product.id, "quantity_change": -2, "reason": "sale"}, format="json")
    body = admin_client.get(MOVEMENTS).json()
    assert body["count"] == 2
    assert admin_client.get(f"{MOVEMENTS}?reason=sale").json()["count"] == 1
    assert admin_client.get(f"{MOVEMENTS}?product={product.id}").json()["count"] == 2


# --- bulk activate/deactivate & duplicate --------------------------------------------------------------


def test_bulk_activate_and_deactivate(admin_client):
    a, b = ProductFactory(status="draft"), ProductFactory(status="draft")
    r = admin_client.post(f"{PRODUCTS}bulk/activate/", {"product_ids": [a.id, b.id]}, format="json")
    assert r.status_code == 200 and r.json()["updated"] == 2
    assert set(Product.objects.values_list("status", flat=True)) == {"published"}
    admin_client.post(f"{PRODUCTS}bulk/deactivate/", {"product_ids": [a.id]}, format="json")
    a.refresh_from_db(); b.refresh_from_db()
    assert a.status == "draft" and b.status == "published"


def test_bulk_activate_requires_ids(admin_client):
    assert admin_client.post(f"{PRODUCTS}bulk/activate/", {"product_ids": []}, format="json").status_code == 400


def test_duplicate_action(admin_client):
    original = ProductFactory(name="Original", sku="ORIG-1")
    r = admin_client.post(f"{PRODUCTS}{original.id}/duplicate/")
    assert r.status_code == 201
    body = r.json()
    assert body["id"] != original.id and body["sku"] == "ORIG-1-copy" and body["status"] == "draft"
    assert Product.objects.count() == 2


# --- attributes & values ------------------------------------------------------------------------------


def test_attribute_and_value_crud(admin_client):
    r = admin_client.post(ATTRIBUTES, {"name": "Shade"}, format="json")
    assert r.status_code == 201 and r.json()["slug"] == "shade"
    attribute_id = r.json()["id"]
    r = admin_client.post(VALUES, {"attribute": attribute_id, "value": "Rose"}, format="json")
    assert r.status_code == 201 and r.json()["slug"] == "rose"
    assert admin_client.get(f"{ATTRIBUTES}{attribute_id}/").json()["values"][0]["value"] == "Rose"
    assert admin_client.get(f"{VALUES}?attribute={attribute_id}").json()["count"] == 1


def test_attribute_names_are_unique(admin_client):
    ProductAttributeFactory(name="Shade")
    r = admin_client.post(ATTRIBUTES, {"name": "shade"}, format="json")
    assert r.status_code == 400 and "name" in details(r)


def test_value_is_unique_per_attribute_but_reusable_across_attributes(admin_client):
    attribute = ProductAttributeFactory()
    other = ProductAttributeFactory()
    AttributeValueFactory(attribute=attribute, value="Small")
    r = admin_client.post(VALUES, {"attribute": attribute.id, "value": "small"}, format="json")
    assert r.status_code == 400 and "value" in details(r)
    r = admin_client.post(VALUES, {"attribute": other.id, "value": "Small"}, format="json")
    assert r.status_code == 201


def test_deleting_an_attribute_cascades_to_its_values():
    attribute = ProductAttributeFactory()
    value = AttributeValueFactory(attribute=attribute)
    attribute.delete()
    from apps.catalog.models import AttributeValue

    assert not AttributeValue.objects.filter(pk=value.pk).exists()
