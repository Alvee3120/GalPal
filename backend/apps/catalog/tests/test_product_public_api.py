import pytest

from apps.catalog import services
from apps.catalog.models import StockStatus

from .factories import (
    AttributeValueFactory,
    BrandFactory,
    CategoryFactory,
    ProductAttributeFactory,
    ProductFactory,
    ProductImageFactory,
    ProductVariantFactory,
    TagFactory,
)

pytestmark = pytest.mark.django_db

PRODUCTS = "/api/v1/products/"


def test_only_published_products_are_public(api_client):
    ProductFactory(status="published", name="Live")
    ProductFactory(status="draft", name="Draft")
    ProductFactory(status="archived", name="Archived")
    body = api_client.get(PRODUCTS).json()
    assert body["count"] == 1 and body["results"][0]["name"] == "Live"


def test_draft_product_detail_is_404(api_client):
    product = ProductFactory(status="draft")
    assert api_client.get(f"{PRODUCTS}{product.slug}/").status_code == 404


def test_list_shape_and_computed_fields(api_client):
    product = ProductFactory(regular_price="100.00", discount_price="80.00", brand=BrandFactory(name="CeraVe"), stock_quantity=5)
    body = api_client.get(PRODUCTS).json()["results"][0]
    assert body["effective_price"] == "80.00" and body["discount_percentage"] == 20 and body["on_sale"] is True
    assert body["brand"]["name"] == "CeraVe" and body["in_stock"] is True
    assert "full_description" not in body and "images" not in body  # list is the compact shape
    assert product.slug == body["slug"]


def test_stale_token_does_not_break_public_products(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
    assert api_client.get(PRODUCTS).status_code == 200


def test_products_are_read_only(api_client):
    product = ProductFactory()
    for method in ("post", "put", "patch", "delete"):
        assert getattr(api_client, method)(PRODUCTS, {}, format="json").status_code == 405
        assert getattr(api_client, method)(f"{PRODUCTS}{product.slug}/", {}, format="json").status_code == 405


# --- detail ------------------------------------------------------------------------------------


def test_detail_includes_gallery_variants_breadcrumb_and_related(api_client):
    root = CategoryFactory(name="Skincare")
    product = ProductFactory(name="Serum")
    services.set_categories(product, [root.id])
    ProductImageFactory(product=product, alt_text="Bottle")
    value = AttributeValueFactory(attribute=ProductAttributeFactory(name="Size"), value="50ml")
    ProductVariantFactory(product=product, attribute_values=[value])
    sibling = ProductFactory(name="Another Serum")
    services.set_categories(sibling, [root.id])
    tag = TagFactory()
    product.tags.set([tag])

    body = api_client.get(f"{PRODUCTS}{product.slug}/").json()
    assert body["images"][0]["alt_text"] == "Bottle"
    assert body["variants"][0]["attribute_values"][0]["value"] == "50ml"
    assert [c["name"] for c in body["breadcrumb"]] == ["Skincare"]
    assert body["categories"][0] == {"id": root.id, "name": root.name, "slug": root.slug, "is_primary": True}
    assert body["tags"][0]["name"] == tag.name
    assert [p["name"] for p in body["related_products"]] == ["Another Serum"]


def test_related_products_exclude_self_and_are_capped(api_client):
    root = CategoryFactory()
    product = ProductFactory()
    services.set_categories(product, [root.id])
    others = ProductFactory.create_batch(10)
    for other in others:
        services.set_categories(other, [root.id])
    related = api_client.get(f"{PRODUCTS}{product.slug}/").json()["related_products"]
    assert len(related) == 8 and product.slug not in {r["slug"] for r in related}


def test_product_with_no_category_has_no_breadcrumb_or_related(api_client):
    product = ProductFactory()
    body = api_client.get(f"{PRODUCTS}{product.slug}/").json()
    assert body["breadcrumb"] == [] and body["related_products"] == []


def test_inactive_variants_are_hidden_from_the_detail(api_client):
    product = ProductFactory()
    ProductVariantFactory(product=product, is_active=False)
    assert api_client.get(f"{PRODUCTS}{product.slug}/").json()["variants"] == []


# --- filters -----------------------------------------------------------------------------------


def test_filter_by_category_includes_descendants(api_client):
    parent = CategoryFactory()
    child = CategoryFactory(parent=parent)
    in_parent, in_child, elsewhere = ProductFactory(), ProductFactory(), ProductFactory()
    services.set_categories(in_parent, [parent.id])
    services.set_categories(in_child, [child.id])
    services.set_categories(elsewhere, [CategoryFactory().id])
    names = {p["name"] for p in api_client.get(f"{PRODUCTS}?category={parent.slug}").json()["results"]}
    assert names == {in_parent.name, in_child.name}


def test_filter_by_unknown_category_is_empty(api_client):
    ProductFactory()
    assert api_client.get(f"{PRODUCTS}?category=nope").json()["count"] == 0


def test_filter_by_brand_and_tag(api_client):
    brand = BrandFactory()
    tag = TagFactory()
    match_brand = ProductFactory(brand=brand)
    match_tag = ProductFactory()
    match_tag.tags.set([tag])
    ProductFactory()
    assert {p["id"] for p in api_client.get(f"{PRODUCTS}?brand={brand.slug}").json()["results"]} == {match_brand.id}
    assert {p["id"] for p in api_client.get(f"{PRODUCTS}?tag={tag.slug}").json()["results"]} == {match_tag.id}


def test_filter_by_price_range_uses_effective_price(api_client):
    cheap = ProductFactory(regular_price="50.00")
    on_sale = ProductFactory(regular_price="500.00", discount_price="60.00")
    expensive = ProductFactory(regular_price="900.00")
    ids = {p["id"] for p in api_client.get(f"{PRODUCTS}?price_min=40&price_max=100").json()["results"]}
    assert ids == {cheap.id, on_sale.id} and expensive.id not in ids


def test_filter_by_skin_type(api_client):
    oily = ProductFactory(skin_type=["oily"])
    ProductFactory(skin_type=["dry"])
    assert {p["id"] for p in api_client.get(f"{PRODUCTS}?skin_type=oily").json()["results"]} == {oily.id}


def test_filter_in_stock(api_client):
    in_stock = ProductFactory(manage_stock=True, stock_quantity=5, stock_status=StockStatus.IN_STOCK)
    out_of_stock = ProductFactory(manage_stock=True, stock_quantity=0, stock_status=StockStatus.OUT_OF_STOCK)
    unmanaged = ProductFactory(manage_stock=False)
    ids = {p["id"] for p in api_client.get(f"{PRODUCTS}?in_stock=true").json()["results"]}
    assert ids == {in_stock.id, unmanaged.id}
    assert {p["id"] for p in api_client.get(f"{PRODUCTS}?in_stock=false").json()["results"]} == {out_of_stock.id}


def test_filter_on_sale(api_client):
    sale = ProductFactory(regular_price="100.00", discount_price="50.00")
    ProductFactory(regular_price="100.00")
    assert {p["id"] for p in api_client.get(f"{PRODUCTS}?on_sale=true").json()["results"]} == {sale.id}


def test_filter_flags(api_client):
    featured = ProductFactory(is_featured=True)
    ProductFactory(is_featured=False)
    assert {p["id"] for p in api_client.get(f"{PRODUCTS}?is_featured=true").json()["results"]} == {featured.id}


def test_search_matches_name_sku_and_brand(api_client):
    brand = BrandFactory(name="La Roche-Posay")
    by_brand = ProductFactory(brand=brand)
    by_sku = ProductFactory(sku="SPECIALSKU123")
    ProductFactory()
    assert {p["id"] for p in api_client.get(f"{PRODUCTS}?search=roche").json()["results"]} == {by_brand.id}
    assert {p["id"] for p in api_client.get(f"{PRODUCTS}?search=SPECIALSKU").json()["results"]} == {by_sku.id}


# --- ordering ----------------------------------------------------------------------------------


def test_ordering_by_price(api_client):
    ProductFactory(regular_price="300.00")
    ProductFactory(regular_price="100.00")
    ProductFactory(regular_price="200.00")
    prices = [p["effective_price"] for p in api_client.get(f"{PRODUCTS}?ordering=price").json()["results"]]
    assert prices == ["100.00", "200.00", "300.00"]
    assert [p["effective_price"] for p in api_client.get(f"{PRODUCTS}?ordering=-price").json()["results"]] == prices[::-1]


def test_ordering_by_price_uses_effective_price_when_on_sale(api_client):
    always_cheap = ProductFactory(regular_price="90.00")
    on_sale = ProductFactory(regular_price="500.00", discount_price="10.00")
    order = [p["id"] for p in api_client.get(f"{PRODUCTS}?ordering=price").json()["results"]]
    assert order == [on_sale.id, always_cheap.id]


def test_ordering_by_rating(api_client):
    from apps.catalog.models import Product

    low = ProductFactory()
    high = ProductFactory()
    Product.objects.filter(pk=high.pk).update(average_rating="4.50")
    order = [p["id"] for p in api_client.get(f"{PRODUCTS}?ordering=-rating").json()["results"]]
    assert order[0] == high.id


def test_ordering_by_popularity_ranks_bestsellers_first(api_client):
    from apps.catalog.models import Product

    normal = ProductFactory()
    Product.objects.filter(pk=normal.pk).update(review_count=1000)
    bestseller = ProductFactory(is_bestseller=True)
    order = [p["id"] for p in api_client.get(f"{PRODUCTS}?ordering=-popularity").json()["results"]]
    assert order[0] == bestseller.id


def test_default_ordering_is_newest_first(api_client):
    first = ProductFactory()
    second = ProductFactory()
    order = [p["id"] for p in api_client.get(PRODUCTS).json()["results"]]
    assert order == [second.id, first.id]


def test_unknown_ordering_falls_back_to_default(api_client):
    ProductFactory()
    assert api_client.get(f"{PRODUCTS}?ordering=nonsense").status_code == 200
