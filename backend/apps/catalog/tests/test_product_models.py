from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.catalog.models import Product, ProductCategory, ProductStatus, ProductVariant, StockStatus

from .factories import (
    AttributeValueFactory,
    BrandFactory,
    CategoryFactory,
    ProductAttributeFactory,
    ProductFactory,
    ProductVariantFactory,
)

pytestmark = pytest.mark.django_db


def test_defaults():
    product = ProductFactory()
    assert product.status == ProductStatus.PUBLISHED and product.stock_status == StockStatus.IN_STOCK
    assert product.stock_quantity == 0 and product.manage_stock is True
    assert product.is_deleted is False and product.has_variants is False
    assert product.average_rating == Decimal("0.00") and product.review_count == 0
    assert str(product) == product.name


def test_feature_image_is_required():
    with pytest.raises(ValidationError):
        Product(name="X", slug="x", sku="X1", regular_price="10.00").full_clean()


def test_sku_is_unique():
    ProductFactory(sku="DUP")
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductFactory(sku="DUP")


def test_regular_price_must_be_positive():
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductFactory(regular_price="0.00")
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductFactory(regular_price="-5.00")


def test_discount_price_must_be_lower_than_regular_at_db_level():
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductFactory(regular_price="100.00", discount_price="100.00")
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductFactory(regular_price="100.00", discount_price="150.00")
    ProductFactory(regular_price="100.00", discount_price="80.00")  # fine


def test_soft_delete_hides_from_default_manager():
    product = ProductFactory()
    product.delete()
    assert not Product.objects.filter(pk=product.pk).exists()
    assert Product.all_objects.filter(pk=product.pk).exists()


# --- price/stock computed properties ------------------------------------------------------------


def test_effective_price_without_discount():
    product = ProductFactory(regular_price="500.00")
    product.refresh_from_db()
    assert product.effective_price == Decimal("500.00") and not product.on_sale and product.discount_percentage == 0


def test_effective_price_with_unconditional_discount():
    product = ProductFactory(regular_price="500.00", discount_price="400.00")
    product.refresh_from_db()
    assert product.on_sale and product.effective_price == Decimal("400.00") and product.discount_percentage == 20


def test_sale_window_controls_on_sale():
    now = timezone.now()
    future = ProductFactory(regular_price="100.00", discount_price="50.00", sale_start_at=now + timedelta(days=1))
    past = ProductFactory(regular_price="100.00", discount_price="50.00", sale_end_at=now - timedelta(days=1))
    active = ProductFactory(
        regular_price="100.00", discount_price="50.00", sale_start_at=now - timedelta(days=1), sale_end_at=now + timedelta(days=1)
    )
    future.refresh_from_db(); past.refresh_from_db(); active.refresh_from_db()
    assert not future.on_sale and future.effective_price == Decimal("100.00")
    assert not past.on_sale and past.effective_price == Decimal("100.00")
    assert active.on_sale and active.effective_price == Decimal("50.00")


def test_in_stock_rules():
    managed = ProductFactory(manage_stock=True, stock_quantity=0, stock_status=StockStatus.OUT_OF_STOCK)
    assert not managed.in_stock
    managed.stock_quantity = 5
    assert managed.in_stock
    unmanaged = ProductFactory(manage_stock=False, stock_quantity=0)
    assert unmanaged.in_stock
    backorder = ProductFactory(manage_stock=True, stock_quantity=0, stock_status=StockStatus.BACKORDER)
    assert backorder.in_stock


def test_low_stock_threshold_falls_back_to_site_settings():
    product = ProductFactory(manage_stock=True, stock_quantity=3, low_stock_threshold=None)
    from apps.site_settings.models import SiteSettings

    SiteSettings.objects.filter(pk=1).update(low_stock_threshold=5)
    assert product.effective_low_stock_threshold == 5 and product.is_low_stock
    product.low_stock_threshold = 1
    assert product.effective_low_stock_threshold == 1 and not product.is_low_stock


# --- categories through-model --------------------------------------------------------------------


def test_only_one_primary_category_per_product():
    product = ProductFactory()
    a, b = CategoryFactory(), CategoryFactory()
    ProductCategory.objects.create(product=product, category=a, is_primary=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductCategory.objects.create(product=product, category=b, is_primary=True)


def test_category_product_count_reflects_real_links():
    category = CategoryFactory()
    products = ProductFactory.create_batch(2)
    for product in products:
        product.categories.set([category])
    assert category.product_count() == 2


def test_soft_deleted_products_do_not_count_towards_the_category():
    category = CategoryFactory()
    product = ProductFactory()
    product.categories.set([category])
    product.delete()
    assert category.product_count() == 0


def test_brand_deletion_nulls_out_the_products_brand():
    brand = BrandFactory()
    product = ProductFactory(brand=brand)
    brand.delete()
    product.refresh_from_db()
    assert product.brand is None


# --- variants ---------------------------------------------------------------------------------


def test_variant_falls_back_to_product_price_and_stock():
    product = ProductFactory(regular_price="200.00", discount_price="150.00")
    variant = ProductVariantFactory(product=product, regular_price=None, discount_price=None)
    variant.refresh_from_db()
    assert variant.regular_price_effective == Decimal("200.00")
    assert variant.discount_price_effective == Decimal("150.00")
    assert variant.on_sale and variant.effective_price == Decimal("150.00")


def test_variant_own_price_overrides_the_product():
    product = ProductFactory(regular_price="200.00", discount_price="150.00")
    variant = ProductVariantFactory(product=product, regular_price="90.00", discount_price=None)
    variant.refresh_from_db()
    assert variant.regular_price_effective == Decimal("90.00") and variant.discount_price_effective is None
    assert not variant.on_sale and variant.effective_price == Decimal("90.00")


def test_variant_sku_is_unique():
    ProductVariantFactory(sku="V-DUP")
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductVariantFactory(sku="V-DUP")


def test_variant_discount_price_must_be_lower_when_both_are_set():
    product = ProductFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductVariantFactory(product=product, regular_price="50.00", discount_price="50.00")


def test_two_variants_of_the_same_product_cannot_share_an_option_combination():
    product = ProductFactory()
    attribute = ProductAttributeFactory()
    rose = AttributeValueFactory(attribute=attribute, value="Rose")
    ProductVariantFactory(product=product, attribute_values=[rose])
    with pytest.raises(IntegrityError), transaction.atomic():
        ProductVariant.objects.create(product=product, sku="another", option_signature=f"{rose.pk}")


def test_the_same_combination_is_fine_on_a_different_product():
    attribute = ProductAttributeFactory()
    rose = AttributeValueFactory(attribute=attribute, value="Rose")
    ProductVariantFactory(attribute_values=[rose])
    ProductVariantFactory(attribute_values=[rose])  # different product: no clash


def test_deleting_a_product_cascades_to_its_variants_and_images():
    product = ProductFactory()
    variant = ProductVariantFactory(product=product)
    from .factories import ProductImageFactory

    image = ProductImageFactory(product=product)
    product.hard_delete()
    assert not ProductVariant.objects.filter(pk=variant.pk).exists()
    assert not product.images.model.objects.filter(pk=image.pk).exists()
