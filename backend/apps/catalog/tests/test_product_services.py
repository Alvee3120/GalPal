from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage

from apps.catalog import services
from apps.catalog.models import Product, ProductCategory, ProductImage, ProductVariant, StockMovement

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


def code_of(exc, field):
    return exc.value.error_dict[field][0].code


# --- SKU uniqueness across products and variants --------------------------------------------------


def test_sku_unique_across_products_and_variants():
    ProductFactory(sku="SHARED")
    with pytest.raises(ValidationError) as exc:
        services.assert_unique_sku("SHARED")
    assert code_of(exc, "sku") == "duplicate_sku"

    ProductVariantFactory(sku="SHARED-2")
    with pytest.raises(ValidationError):
        services.assert_unique_sku("SHARED-2")


def test_sku_check_excludes_self_on_update():
    product = ProductFactory(sku="MINE")
    services.assert_unique_sku("MINE", exclude_product=product)
    variant = ProductVariantFactory(sku="MINE-V")
    services.assert_unique_sku("MINE-V", exclude_variant=variant)


# --- categories -----------------------------------------------------------------------------------


def test_set_categories_creates_links_and_defaults_primary_to_first():
    product = ProductFactory()
    a, b = CategoryFactory(), CategoryFactory()
    services.set_categories(product, [a.id, b.id])
    links = {link.category_id: link.is_primary for link in product.category_links.all()}
    assert links == {a.id: True, b.id: False}


def test_set_categories_honours_explicit_primary():
    product = ProductFactory()
    a, b = CategoryFactory(), CategoryFactory()
    services.set_categories(product, [a.id, b.id], primary_id=b.id)
    assert ProductCategory.objects.get(product=product, category=b).is_primary
    assert not ProductCategory.objects.get(product=product, category=a).is_primary


def test_set_categories_replaces_the_previous_set():
    product = ProductFactory()
    a, b, c = CategoryFactory(), CategoryFactory(), CategoryFactory()
    services.set_categories(product, [a.id, b.id])
    services.set_categories(product, [b.id, c.id])
    assert set(product.category_links.values_list("category_id", flat=True)) == {b.id, c.id}


def test_set_categories_rejects_unknown_id():
    product = ProductFactory()
    with pytest.raises(ValidationError) as exc:
        services.set_categories(product, [999999])
    assert code_of(exc, "categories") == "not_found"


def test_set_categories_rejects_primary_not_in_list():
    product = ProductFactory()
    a, b = CategoryFactory(), CategoryFactory()
    with pytest.raises(ValidationError) as exc:
        services.set_categories(product, [a.id], primary_id=b.id)
    assert code_of(exc, "primary_category") == "invalid_primary"


def test_set_categories_to_empty_list_clears_them():
    product = ProductFactory()
    services.set_categories(product, [CategoryFactory().id])
    services.set_categories(product, [])
    assert not product.category_links.exists()


# --- variant options --------------------------------------------------------------------------------


def test_set_variant_options_stores_a_sorted_signature():
    variant = ProductVariantFactory()
    attribute = ProductAttributeFactory()
    a, b = AttributeValueFactory(attribute=attribute), AttributeValueFactory(attribute=attribute)
    services.set_variant_options(variant, [b.pk, a.pk])
    variant.refresh_from_db()
    assert variant.option_signature == services.option_signature([a.pk, b.pk])
    assert set(variant.attribute_values.values_list("pk", flat=True)) == {a.pk, b.pk}


def test_set_variant_options_rejects_unknown_value():
    variant = ProductVariantFactory()
    with pytest.raises(ValidationError) as exc:
        services.set_variant_options(variant, [999999])
    assert code_of(exc, "attribute_values") == "not_found"


def test_set_variant_options_rejects_duplicate_combination_on_same_product():
    product = ProductFactory()
    value = AttributeValueFactory()
    ProductVariantFactory(product=product, attribute_values=[value])
    other = ProductVariantFactory(product=product)
    with pytest.raises(ValidationError) as exc:
        services.set_variant_options(other, [value.pk])
    assert code_of(exc, "attribute_values") == "duplicate_combination"


def test_set_variant_options_allows_updating_a_variant_to_keep_its_own_combination():
    value = AttributeValueFactory()
    variant = ProductVariantFactory(attribute_values=[value])
    services.set_variant_options(variant, [value.pk])  # no-op re-set must not clash with itself


# --- stock -------------------------------------------------------------------------------------------


def test_adjust_stock_increases_and_logs():
    product = ProductFactory(stock_quantity=0)
    updated, movement = services.adjust_stock(product=product, quantity_change=10, reason="restock", reference="PO-1")
    assert updated.stock_quantity == 10 and updated.stock_status == "in_stock"
    assert movement.quantity_change == 10 and movement.balance_after == 10 and movement.reference == "PO-1"
    assert StockMovement.objects.count() == 1


def test_adjust_stock_decreases_and_sets_out_of_stock_at_zero():
    product = ProductFactory(stock_quantity=5)
    updated, _ = services.adjust_stock(product=product, quantity_change=-5, reason="sale")
    assert updated.stock_quantity == 0 and updated.stock_status == "out_of_stock"


def test_adjust_stock_refuses_to_go_negative():
    product = ProductFactory(stock_quantity=2)
    with pytest.raises(ValidationError) as exc:
        services.adjust_stock(product=product, quantity_change=-5, reason="sale")
    assert code_of(exc, "quantity_change") == "insufficient_stock"
    product.refresh_from_db()
    assert product.stock_quantity == 2 and StockMovement.objects.count() == 0


def test_adjust_stock_refuses_when_stock_is_not_managed():
    product = ProductFactory(manage_stock=False, stock_quantity=0)
    with pytest.raises(ValidationError) as exc:
        services.adjust_stock(product=product, quantity_change=1, reason="restock")
    assert code_of(exc, "quantity_change") == "stock_not_managed"


def test_backorder_status_is_not_cleared_automatically_by_restocking():
    product = ProductFactory(stock_quantity=0, stock_status="backorder")
    updated, _ = services.adjust_stock(product=product, quantity_change=5, reason="restock")
    assert updated.stock_status == "backorder"


def test_adjust_stock_on_a_variant_does_not_touch_product_stock():
    product = ProductFactory(stock_quantity=100)
    variant = ProductVariantFactory(product=product, stock_quantity=0)
    updated, movement = services.adjust_stock(variant=variant, product=product, quantity_change=3, reason="restock")
    assert updated.stock_quantity == 3 and movement.variant_id == variant.pk and movement.product_id == product.pk
    product.refresh_from_db()
    assert product.stock_quantity == 100


def test_adjust_stock_locks_the_row(django_capture_on_commit_callbacks):
    """Two adjustments in sequence must both be reflected (no lost update)."""
    product = ProductFactory(stock_quantity=10)
    services.adjust_stock(product=product, quantity_change=-3, reason="sale")
    services.adjust_stock(product=product, quantity_change=-2, reason="sale")
    product.refresh_from_db()
    assert product.stock_quantity == 5
    assert list(StockMovement.objects.values_list("balance_after", flat=True).order_by("id")) == [7, 5]


# --- bulk status ---------------------------------------------------------------------------------------


def test_bulk_set_status():
    products = ProductFactory.create_batch(3, status="draft")
    updated = services.bulk_set_status([p.pk for p in products], "published")
    assert updated == 3
    assert set(Product.objects.values_list("status", flat=True)) == {"published"}


def test_bulk_set_status_ignores_unknown_ids():
    product = ProductFactory(status="draft")
    updated = services.bulk_set_status([product.pk, 999999], "published")
    assert updated == 1


# --- duplication -----------------------------------------------------------------------------------


def test_duplicate_copies_scalars_as_a_fresh_draft():
    brand = BrandFactory()
    original = ProductFactory(
        name="Original", sku="ORIG", regular_price="300.00", discount_price="250.00",
        brand=brand, status="published", stock_quantity=50,
    )
    copy = services.duplicate_product(original)
    copy.refresh_from_db()
    assert copy.pk != original.pk
    assert copy.name == "Original (Copy)" and copy.slug != original.slug
    assert copy.sku == "ORIG-copy" and copy.status == "draft" and copy.stock_quantity == 0
    assert copy.regular_price == Decimal("300.00") and copy.discount_price == Decimal("250.00")
    assert copy.brand == brand


def test_duplicate_sku_is_de_duplicated_on_repeat():
    original = ProductFactory(sku="AGAIN")
    first = services.duplicate_product(original)
    second = services.duplicate_product(original)
    assert {first.sku, second.sku} == {"AGAIN-copy", "AGAIN-copy-2"}


def test_duplicate_copies_categories_tags_images_and_variants():
    original = ProductFactory()
    category = CategoryFactory()
    original.categories.set([category])
    tag = TagFactory()
    original.tags.set([tag])
    ProductImageFactory(product=original, alt_text="hero")
    value = AttributeValueFactory()
    ProductVariantFactory(product=original, sku="ORIG-V", attribute_values=[value], stock_quantity=9)

    copy = services.duplicate_product(original)

    assert list(copy.tags.values_list("pk", flat=True)) == [tag.pk]
    assert list(copy.categories.values_list("pk", flat=True)) == [category.pk]
    assert copy.images.count() == 1 and copy.images.first().alt_text == "hero"
    assert copy.images.first().image.name != original.images.first().image.name  # independent file

    variant = copy.variants.get()
    assert variant.sku == "ORIG-V-copy" and variant.stock_quantity == 0
    assert list(variant.attribute_values.values_list("pk", flat=True)) == [value.pk]


def test_duplicate_feature_image_is_an_independent_file():
    original = ProductFactory()
    copy = services.duplicate_product(original)
    assert copy.feature_image.name != original.feature_image.name
    assert default_storage.exists(copy.feature_image.name) and default_storage.exists(original.feature_image.name)


def test_deleting_the_original_does_not_affect_the_duplicates_files():
    original = ProductFactory()
    copy = services.duplicate_product(original)
    copy_image_name = copy.feature_image.name
    original.hard_delete()
    assert default_storage.exists(copy_image_name)
