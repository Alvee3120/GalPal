import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from .factories import BrandFactory, CategoryFactory, TagFactory

pytestmark = pytest.mark.django_db

CATEGORIES = "/api/v1/categories/"
TREE = "/api/v1/categories/tree/"
BRANDS = "/api/v1/brands/"
TAGS = "/api/v1/tags/"

CATEGORY_LIST_FIELDS = {"id", "name", "slug", "image", "parent", "description", "sort_order"}
CATEGORY_DETAIL_FIELDS = CATEGORY_LIST_FIELDS | {"seo_title", "seo_description", "breadcrumb", "children"}


def png(name="c.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue())


def menu():
    """skincare(1) > [serums(1) > [vitamin-c(1)], cleansers(2)],  makeup(2),  hidden(3, inactive) > secret"""
    skincare = CategoryFactory(name="Skincare", sort_order=1)
    serums = CategoryFactory(name="Serums", parent=skincare, sort_order=1)
    vit_c = CategoryFactory(name="Vitamin C", parent=serums, sort_order=1)
    cleansers = CategoryFactory(name="Cleansers", parent=skincare, sort_order=2)
    makeup = CategoryFactory(name="Makeup", sort_order=2)
    hidden = CategoryFactory(name="Hidden", sort_order=3, is_active=False)
    secret = CategoryFactory(name="Secret", parent=hidden)
    return dict(skincare=skincare, serums=serums, vit_c=vit_c, cleansers=cleansers, makeup=makeup, hidden=hidden, secret=secret)


# --- tree -------------------------------------------------------------------------------------------


def test_tree_nests_children_in_display_order(api_client):
    menu()
    tree = api_client.get(TREE).json()
    assert [n["name"] for n in tree] == ["Skincare", "Makeup"]
    skincare = tree[0]
    assert [c["name"] for c in skincare["children"]] == ["Serums", "Cleansers"]
    assert [c["name"] for c in skincare["children"][0]["children"]] == ["Vitamin C"]
    assert skincare["children"][0]["children"][0]["children"] == [] and tree[1]["children"] == []


def test_tree_is_a_plain_array_not_paginated(api_client):
    menu()
    body = api_client.get(TREE).json()
    assert isinstance(body, list)


def test_tree_hides_inactive_categories_and_their_whole_subtree(api_client):
    menu()
    raw = api_client.get(TREE).content.decode()
    assert "Hidden" not in raw and "Secret" not in raw


def test_tree_hides_a_visible_child_of_an_inactive_middle_node(api_client):
    m = menu()
    m["serums"].is_active = False
    m["serums"].save()
    raw = api_client.get(TREE).content.decode()
    assert "Serums" not in raw and "Vitamin C" not in raw and "Cleansers" in raw


def test_tree_nodes_expose_only_public_fields(api_client):
    menu()
    node = api_client.get(TREE).json()[0]
    assert set(node) == CATEGORY_LIST_FIELDS | {"children"}
    assert "is_active" not in node and "seo_title" not in node


def test_tree_parent_is_the_parent_slug(api_client):
    m = menu()
    tree = api_client.get(TREE).json()
    assert tree[0]["parent"] is None and tree[0]["children"][0]["parent"] == m["skincare"].slug


def test_empty_tree_is_an_empty_list(api_client):
    assert api_client.get(TREE).json() == []


def test_tree_uses_a_constant_number_of_queries(api_client, django_assert_max_num_queries):
    menu()
    with django_assert_max_num_queries(3):
        api_client.get(TREE)
    for i in range(40):
        CategoryFactory(parent=CategoryFactory(name=f"Extra root {i}"), name=f"Extra child {i}")
    with django_assert_max_num_queries(3):
        assert len(api_client.get(TREE).json()) > 40


def test_a_very_deep_tree_renders(api_client):
    parent = None
    for _ in range(150):
        parent = CategoryFactory(parent=parent)
    node, depth = api_client.get(TREE).json()[0], 1
    while node["children"]:
        node, depth = node["children"][0], depth + 1
    assert depth == 150


def test_images_are_absolute_urls(api_client):
    CategoryFactory(name="With Image", image=png())
    CategoryFactory(name="No Image")
    nodes = {n["name"]: n for n in api_client.get(TREE).json()}
    image = nodes["With Image"]["image"]
    assert image.startswith("http://testserver/media/categories/") and image.endswith(".png")
    assert nodes["No Image"]["image"] is None


# --- flat list ----------------------------------------------------------------------------------------


def test_flat_list_is_paginated_and_only_visible(api_client):
    menu()
    body = api_client.get(CATEGORIES).json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 5 and {r["name"] for r in body["results"]} == {"Skincare", "Serums", "Vitamin C", "Cleansers", "Makeup"}
    assert set(body["results"][0]) == CATEGORY_LIST_FIELDS


def test_flat_list_default_order_is_sort_order_then_name(api_client):
    menu()
    names = [r["name"] for r in api_client.get(CATEGORIES).json()["results"]]
    assert names == sorted(names, key=lambda n: ({"Skincare": 1, "Serums": 1, "Vitamin C": 1, "Cleansers": 2, "Makeup": 2}[n], n))


def test_filter_by_parent_slug(api_client):
    m = menu()
    r = api_client.get(f"{CATEGORIES}?parent={m['skincare'].slug}").json()
    assert {c["name"] for c in r["results"]} == {"Serums", "Cleansers"}
    assert api_client.get(f"{CATEGORIES}?parent=no-such-parent").json()["count"] == 0


def test_filter_top_level(api_client):
    menu()
    assert {c["name"] for c in api_client.get(f"{CATEGORIES}?top_level=true").json()["results"]} == {"Skincare", "Makeup"}
    assert api_client.get(f"{CATEGORIES}?top_level=false").json()["count"] == 3


def test_search_by_name(api_client):
    menu()
    assert [c["name"] for c in api_client.get(f"{CATEGORIES}?search=vitamin").json()["results"]] == ["Vitamin C"]
    assert api_client.get(f"{CATEGORIES}?search=secret").json()["count"] == 0  # hidden stays hidden


def test_ordering_and_page_size(api_client):
    menu()
    names = [c["name"] for c in api_client.get(f"{CATEGORIES}?ordering=-name").json()["results"]]
    assert names == sorted(names, reverse=True)
    body = api_client.get(f"{CATEGORIES}?page_size=2").json()
    assert len(body["results"]) == 2 and body["next"] is not None


def test_flat_list_query_count_does_not_grow_with_rows(api_client, django_assert_max_num_queries):
    menu()
    with django_assert_max_num_queries(4):
        api_client.get(CATEGORIES)
    for i in range(30):
        CategoryFactory(parent=CategoryFactory(name=f"R{i}"), name=f"C{i}")
    with django_assert_max_num_queries(4):
        api_client.get(f"{CATEGORIES}?page_size=100")


# --- detail -------------------------------------------------------------------------------------------


def test_detail_by_slug_has_breadcrumb_children_and_seo(api_client):
    m = menu()
    m["serums"].seo_title, m["serums"].seo_description = "Best serums", "Shop serums"
    m["serums"].description = "All our serums"
    m["serums"].save()
    body = api_client.get(f"{CATEGORIES}{m['serums'].slug}/").json()
    assert set(body) == CATEGORY_DETAIL_FIELDS
    assert body["seo_title"] == "Best serums" and body["seo_description"] == "Shop serums" and body["description"] == "All our serums"
    assert [b["name"] for b in body["breadcrumb"]] == ["Skincare", "Serums"]
    assert body["breadcrumb"][0] == {"id": m["skincare"].id, "name": "Skincare", "slug": m["skincare"].slug}
    assert [c["name"] for c in body["children"]] == ["Vitamin C"]
    assert body["parent"] == m["skincare"].slug


def test_detail_children_exclude_inactive_ones(api_client):
    m = menu()
    CategoryFactory(name="Draft", parent=m["skincare"], is_active=False)
    body = api_client.get(f"{CATEGORIES}{m['skincare'].slug}/").json()
    assert [c["name"] for c in body["children"]] == ["Serums", "Cleansers"]


def test_detail_of_a_top_level_category(api_client):
    m = menu()
    body = api_client.get(f"{CATEGORIES}{m['makeup'].slug}/").json()
    assert [b["name"] for b in body["breadcrumb"]] == ["Makeup"] and body["children"] == [] and body["parent"] is None


def test_inactive_category_and_its_descendants_are_404(api_client):
    m = menu()
    for key in ("hidden", "secret"):
        r = api_client.get(f"{CATEGORIES}{m[key].slug}/")
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_unknown_slug_is_404(api_client):
    assert api_client.get(f"{CATEGORIES}nope/").status_code == 404


def test_detail_query_count_is_small(api_client, django_assert_max_num_queries):
    m = menu()
    with django_assert_max_num_queries(3):
        api_client.get(f"{CATEGORIES}{m['vit_c'].slug}/")


# --- access ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("url", [CATEGORIES, TREE, BRANDS, TAGS])
def test_public_endpoints_are_open_and_ignore_stale_tokens(api_client, url):
    assert api_client.get(url).status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION="Bearer expired.or.garbage")
    assert api_client.get(url).status_code == 200


@pytest.mark.parametrize("url", [CATEGORIES, TREE, BRANDS, TAGS])
def test_public_endpoints_are_read_only(api_client, auth_client, admin_user, url):
    for client in (api_client, auth_client(admin_user)):
        for method in ("post", "put", "patch", "delete"):
            assert getattr(client, method)(url, {}, format="json").status_code == 405


def test_detail_endpoints_are_read_only(api_client):
    c = CategoryFactory()
    for method in ("post", "put", "patch", "delete"):
        assert getattr(api_client, method)(f"{CATEGORIES}{c.slug}/", {}, format="json").status_code == 405


# --- brands ---------------------------------------------------------------------------------------------


def test_brands_list_only_active_with_public_fields(api_client):
    BrandFactory(name="Visible", description="Nice", logo=png("b.png"))
    BrandFactory(name="Gone", is_active=False)
    body = api_client.get(BRANDS).json()
    assert set(body) == {"count", "next", "previous", "results"} and body["count"] == 1
    brand = body["results"][0]
    assert set(brand) == {"id", "name", "slug", "logo", "description"}
    assert brand["logo"].startswith("http://testserver/media/brands/")
    assert "is_active" not in brand


def test_brand_detail_by_slug_and_inactive_is_404(api_client):
    live, dead = BrandFactory(name="Live"), BrandFactory(name="Dead", is_active=False)
    assert api_client.get(f"{BRANDS}{live.slug}/").json()["name"] == "Live"
    assert api_client.get(f"{BRANDS}{dead.slug}/").status_code == 404


def test_brand_search_and_ordering(api_client):
    BrandFactory(name="Zeta"), BrandFactory(name="Alpha"), BrandFactory(name="Beta")
    assert [b["name"] for b in api_client.get(BRANDS).json()["results"]] == ["Alpha", "Beta", "Zeta"]
    assert [b["name"] for b in api_client.get(f"{BRANDS}?search=et").json()["results"]] == ["Beta", "Zeta"]
    assert [b["name"] for b in api_client.get(f"{BRANDS}?ordering=-name").json()["results"]][0] == "Zeta"


# --- tags -----------------------------------------------------------------------------------------------


def test_tags_list_and_detail(api_client):
    TagFactory(name="Vegan"), TagFactory(name="Cruelty Free")
    body = api_client.get(TAGS).json()
    assert body["count"] == 2 and [t["name"] for t in body["results"]] == ["Cruelty Free", "Vegan"]
    assert set(body["results"][0]) == {"id", "name", "slug"}
    assert api_client.get(f"{TAGS}vegan/").json()["name"] == "Vegan"
    assert api_client.get(f"{TAGS}missing/").status_code == 404
    assert [t["name"] for t in api_client.get(f"{TAGS}?search=free").json()["results"]] == ["Cruelty Free"]
