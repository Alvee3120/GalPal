import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError, F

from apps.catalog.models import Brand, Category, Tag

from .factories import BrandFactory, CategoryFactory, TagFactory

pytestmark = pytest.mark.django_db


def test_defaults_and_str():
    category = CategoryFactory(name="Serums")
    assert str(category) == "Serums" and category.is_active and category.sort_order == 0
    assert category.created_at and category.updated_at and category.slug_is_custom is False
    assert str(BrandFactory(name="CeraVe")) == "CeraVe" and str(TagFactory(name="vegan")) == "vegan"


def test_categories_are_ordered_by_sort_order_then_name():
    b, a, first = CategoryFactory(name="B", sort_order=1), CategoryFactory(name="A", sort_order=1), CategoryFactory(name="Z", sort_order=0)
    assert list(Category.objects.all()) == [first, a, b]


def test_nesting_has_no_depth_limit():
    parent = None
    for depth in range(60):
        parent = CategoryFactory(parent=parent)
    assert Category.objects.count() == 60 and parent.parent.parent.pk


def test_slug_is_unique_across_categories():
    CategoryFactory(name="One", slug="same")
    with pytest.raises(IntegrityError), transaction.atomic():
        CategoryFactory(name="Two", slug="same")


def test_a_category_cannot_be_its_own_parent_in_the_database():
    category = CategoryFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        Category.objects.filter(pk=category.pk).update(parent=F("id"))


def test_sibling_names_are_unique_ignoring_case():
    parent = CategoryFactory()
    CategoryFactory(name="Serum", slug="serum-a", parent=parent)
    with pytest.raises(IntegrityError), transaction.atomic():
        CategoryFactory(name="SERUM", slug="serum-b", parent=parent)


def test_top_level_names_are_unique_even_though_parent_is_null():
    CategoryFactory(name="Skincare", slug="skincare")
    with pytest.raises(IntegrityError), transaction.atomic():
        CategoryFactory(name="skincare", slug="skincare-2")


def test_same_name_is_fine_under_different_parents():
    a, b = CategoryFactory(name="Face"), CategoryFactory(name="Hair")
    CategoryFactory(name="Serum", slug="face-serum", parent=a)
    CategoryFactory(name="Serum", slug="hair-serum", parent=b)
    CategoryFactory(name="Serum", slug="serum")  # and at the top level
    assert Category.objects.filter(name="Serum").count() == 3


def test_database_refuses_to_delete_a_category_that_has_children():
    parent = CategoryFactory()
    CategoryFactory(parent=parent)
    with pytest.raises(ProtectedError):
        parent.delete()
    assert Category.objects.count() == 2


def test_brand_and_tag_names_are_unique_ignoring_case():
    BrandFactory(name="CeraVe", slug="cerave")
    TagFactory(name="Vegan", slug="vegan")
    with pytest.raises(IntegrityError), transaction.atomic():
        BrandFactory(name="cerave", slug="cerave-2")
    with pytest.raises(IntegrityError), transaction.atomic():
        TagFactory(name="VEGAN", slug="vegan-2")


def test_slugs_are_unique_for_brands_and_tags():
    BrandFactory(name="A", slug="x")
    TagFactory(name="B", slug="y")
    with pytest.raises(IntegrityError), transaction.atomic():
        BrandFactory(name="C", slug="x")
    with pytest.raises(IntegrityError), transaction.atomic():
        TagFactory(name="D", slug="y")


def test_product_count_is_zero_until_products_exist(monkeypatch):
    category = CategoryFactory()
    assert category.product_count() == 0

    class FakeProducts:
        def count(self):
            return 4

    # what Module 4's Product.categories(related_name="products") will provide
    monkeypatch.setattr(Category, "products", property(lambda self: FakeProducts()), raising=False)
    assert category.product_count() == 4


def test_brand_defaults():
    brand = Brand.objects.create(name="X", slug="x")
    assert brand.is_active and not brand.logo and brand.description == ""
    assert Tag.objects.create(name="t", slug="t").pk
