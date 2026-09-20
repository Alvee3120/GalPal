import io

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.catalog.models import Brand, Category, Tag

from .factories import BrandFactory, CategoryFactory, TagFactory

pytestmark = pytest.mark.django_db

CATEGORIES = "/api/v1/admin/categories/"
BRANDS = "/api/v1/admin/brands/"
TAGS = "/api/v1/admin/tags/"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


def png(name="a.png", fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "pink").save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue())


def details(response):
    return response.json()["error"]["details"]


# --- access control ------------------------------------------------------------------------------------


@pytest.mark.parametrize("url", [CATEGORIES, BRANDS, TAGS, f"{CATEGORIES}tree/"])
def test_anonymous_customer_and_cce_are_locked_out(api_client, auth_client, customer, cce_user, url):
    assert api_client.get(url).status_code == 401
    for user in (customer, cce_user):
        client = auth_client(user)
        assert client.get(url).status_code == 403
        assert client.post(url, {"name": "X"}, format="json").status_code == 403


def test_cce_cannot_modify_or_delete_anything(auth_client, cce_user):
    category, brand, tag = CategoryFactory(), BrandFactory(), TagFactory()
    client = auth_client(cce_user)
    for base, obj in [(CATEGORIES, category), (BRANDS, brand), (TAGS, tag)]:
        assert client.patch(f"{base}{obj.pk}/", {"name": "Hacked"}, format="json").status_code == 403
        assert client.delete(f"{base}{obj.pk}/").status_code == 403
    assert Category.objects.get().name == category.name and Brand.objects.count() == 1 and Tag.objects.count() == 1


@pytest.mark.parametrize("url", [CATEGORIES, BRANDS, TAGS])
def test_put_is_not_supported(admin_client, url):
    assert admin_client.put(f"{url}1/", {}, format="json").status_code == 405


# --- categories: create / read ---------------------------------------------------------------------------


def test_create_top_level_category(admin_client):
    r = admin_client.post(CATEGORIES, {"name": "Skincare", "description": "All skincare", "sort_order": 3, "seo_title": "Skincare | GalPal", "seo_description": "Buy skincare"}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "skincare" and body["parent"] is None and body["is_active"] is True and body["sort_order"] == 3
    assert body["children_count"] == 0 and body["products_count"] == 0
    assert set(body) == {"id", "name", "slug", "image", "parent", "description", "is_active", "sort_order", "seo_title", "seo_description", "children_count", "products_count", "created_at", "updated_at"}


def test_create_child_category(admin_client):
    parent = CategoryFactory(name="Skincare")
    r = admin_client.post(CATEGORIES, {"name": "Serums", "parent": parent.id}, format="json")
    assert r.status_code == 201 and r.json()["parent"] == parent.id
    assert Category.objects.get(name="Serums").parent == parent


def test_name_is_required_and_trimmed(admin_client):
    assert "name" in details(admin_client.post(CATEGORIES, {}, format="json"))
    assert "name" in details(admin_client.post(CATEGORIES, {"name": "   "}, format="json"))
    r = admin_client.post(CATEGORIES, {"name": "  Padded  "}, format="json")
    assert r.json()["name"] == "Padded"
    assert "name" in details(admin_client.post(CATEGORIES, {"name": "x" * 121}, format="json"))


def test_unknown_parent_is_a_field_error(admin_client):
    r = admin_client.post(CATEGORIES, {"name": "X", "parent": 99999}, format="json")
    assert r.status_code == 400 and "parent" in details(r)


def test_seo_field_lengths_and_negative_sort_order_are_validated(admin_client):
    for field, value in [("seo_title", "x" * 71), ("seo_description", "x" * 321), ("sort_order", -1)]:
        r = admin_client.post(CATEGORIES, {"name": "X", field: value}, format="json")
        assert r.status_code == 400 and field in details(r), field


def test_list_includes_inactive_with_children_counts_and_is_paginated(admin_client):
    root = CategoryFactory(name="Root")
    CategoryFactory.create_batch(3, parent=root)
    CategoryFactory(name="Off", is_active=False)
    body = admin_client.get(CATEGORIES).json()
    assert set(body) == {"count", "next", "previous", "results"} and body["count"] == 5
    counts = {c["name"]: c["children_count"] for c in body["results"]}
    assert counts["Root"] == 3 and counts["Off"] == 0


def test_list_filters_search_and_ordering(admin_client):
    root = CategoryFactory(name="Skincare", sort_order=2)
    child = CategoryFactory(name="Serums", parent=root, sort_order=1)
    off = CategoryFactory(name="Discontinued", is_active=False)
    ids = lambda qs: {c["id"] for c in admin_client.get(f"{CATEGORIES}?{qs}").json()["results"]}  # noqa: E731
    assert ids("is_active=false") == {off.id}
    assert ids(f"parent={root.id}") == {child.id}
    assert ids("top_level=true") == {root.id, off.id}
    assert ids("search=serum") == {child.id}
    assert ids(f"search={root.slug}") == {root.id}
    assert [c["id"] for c in admin_client.get(f"{CATEGORIES}?ordering=-sort_order").json()["results"]][0] == root.id


def test_list_query_count_is_constant(admin_client, django_assert_max_num_queries):
    CategoryFactory.create_batch(3)
    with django_assert_max_num_queries(6):
        admin_client.get(CATEGORIES)
    CategoryFactory.create_batch(20)
    with django_assert_max_num_queries(6):
        admin_client.get(f"{CATEGORIES}?page_size=100")


def test_retrieve_category(admin_client):
    parent = CategoryFactory(name="P")
    child = CategoryFactory(name="C", parent=parent)
    body = admin_client.get(f"{CATEGORIES}{parent.id}/").json()
    assert body["id"] == parent.id and body["children_count"] == 1
    assert admin_client.get(f"{CATEGORIES}{child.id}/").json()["parent"] == parent.id
    assert admin_client.get(f"{CATEGORIES}99999/").status_code == 404


def test_admin_tree_includes_inactive_categories(admin_client):
    root = CategoryFactory(name="Root", sort_order=1)
    off = CategoryFactory(name="Off", parent=root, is_active=False)
    CategoryFactory(name="Deep", parent=off)
    tree = admin_client.get(f"{CATEGORIES}tree/").json()
    assert isinstance(tree, list) and tree[0]["name"] == "Root"
    assert tree[0]["children"][0]["is_active"] is False and tree[0]["children"][0]["children"][0]["name"] == "Deep"
    assert set(tree[0]) == {"id", "name", "slug", "image", "parent", "is_active", "sort_order", "children"}


# --- categories: update / moving ----------------------------------------------------------------------------


def test_patch_updates_only_sent_fields(admin_client):
    c = CategoryFactory(name="Old", description="keep me", sort_order=4)
    r = admin_client.patch(f"{CATEGORIES}{c.id}/", {"is_active": False}, format="json")
    assert r.status_code == 200
    c.refresh_from_db()
    assert not c.is_active and c.description == "keep me" and c.sort_order == 4 and c.name == "Old"


def test_move_a_category_under_another(admin_client):
    a, b = CategoryFactory(), CategoryFactory()
    assert admin_client.patch(f"{CATEGORIES}{a.id}/", {"parent": b.id}, format="json").status_code == 200
    a.refresh_from_db()
    assert a.parent == b
    assert admin_client.patch(f"{CATEGORIES}{a.id}/", {"parent": None}, format="json").status_code == 200
    a.refresh_from_db()
    assert a.parent is None


def test_cannot_make_a_category_its_own_parent(admin_client):
    c = CategoryFactory()
    r = admin_client.patch(f"{CATEGORIES}{c.id}/", {"parent": c.id}, format="json")
    assert r.status_code == 400 and details(r) == {"parent": ["A category cannot be its own parent."]}
    c.refresh_from_db()
    assert c.parent is None


def test_cannot_move_a_category_under_its_own_child_or_deep_descendant(admin_client):
    a = CategoryFactory()
    b = CategoryFactory(parent=a)
    c = CategoryFactory(parent=b)
    d = CategoryFactory(parent=c)
    for target in (b, c, d):
        r = admin_client.patch(f"{CATEGORIES}{a.id}/", {"parent": target.id}, format="json")
        assert r.status_code == 400 and list(details(r)) == ["parent"], target
        assert details(r)["parent"] == ["A category cannot be moved under one of its own descendants."]
    a.refresh_from_db()
    assert a.parent is None
    # the other direction is fine: promote d directly under a
    assert admin_client.patch(f"{CATEGORIES}{d.id}/", {"parent": a.id}, format="json").status_code == 200


def test_sibling_names_must_be_unique_ignoring_case(admin_client):
    parent = CategoryFactory()
    CategoryFactory(name="Serum", slug="serum-1", parent=parent)
    r = admin_client.post(CATEGORIES, {"name": "SERUM", "parent": parent.id}, format="json")
    assert r.status_code == 400 and "name" in details(r)
    # same name elsewhere is fine
    assert admin_client.post(CATEGORIES, {"name": "Serum"}, format="json").status_code == 201


def test_top_level_names_must_be_unique(admin_client):
    CategoryFactory(name="Skincare")
    assert admin_client.post(CATEGORIES, {"name": "skincare"}, format="json").status_code == 400


def test_renaming_to_an_existing_sibling_name_is_rejected_but_own_name_is_fine(admin_client):
    parent = CategoryFactory()
    CategoryFactory(name="Taken", slug="t1", parent=parent)
    mine = CategoryFactory(name="Mine", slug="m1", parent=parent)
    assert admin_client.patch(f"{CATEGORIES}{mine.id}/", {"name": "taken"}, format="json").status_code == 400
    assert admin_client.patch(f"{CATEGORIES}{mine.id}/", {"name": "Mine"}, format="json").status_code == 200
    assert admin_client.patch(f"{CATEGORIES}{mine.id}/", {"name": "MINE"}, format="json").status_code == 200  # case change of itself


def test_moving_into_a_parent_that_already_has_that_name_is_rejected(admin_client):
    target = CategoryFactory()
    CategoryFactory(name="Serum", slug="s-in-target", parent=target)
    mover = CategoryFactory(name="serum", slug="s-mover")
    r = admin_client.patch(f"{CATEGORIES}{mover.id}/", {"parent": target.id}, format="json")
    assert r.status_code == 400 and "name" in details(r)


def test_deactivating_a_parent_hides_the_subtree_publicly(admin_client, api_client):
    parent = CategoryFactory(name="Parent")
    CategoryFactory(name="Kid", parent=parent)
    assert "Kid" in api_client.get("/api/v1/categories/tree/").content.decode()
    admin_client.patch(f"{CATEGORIES}{parent.id}/", {"is_active": False}, format="json")
    assert api_client.get("/api/v1/categories/tree/").json() == []


# --- categories: delete -----------------------------------------------------------------------------------------


def test_delete_leaf_category(admin_client):
    c = CategoryFactory()
    assert admin_client.delete(f"{CATEGORIES}{c.id}/").status_code == 204
    assert not Category.objects.exists()


def test_delete_is_blocked_by_children_with_a_helpful_409(admin_client):
    parent = CategoryFactory()
    CategoryFactory.create_batch(2, parent=parent)
    r = admin_client.delete(f"{CATEGORIES}{parent.id}/")
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "category_has_children" and error["details"] == {"children_count": 2}
    assert "move_children_to" in error["message"]
    assert Category.objects.count() == 3


def test_delete_is_blocked_by_products(admin_client, monkeypatch):
    class Products:
        def count(self):
            return 7

    monkeypatch.setattr(Category, "products", property(lambda self: Products()), raising=False)
    c = CategoryFactory()
    r = admin_client.delete(f"{CATEGORIES}{c.id}/")
    assert r.status_code == 409 and r.json()["error"]["code"] == "category_has_products"
    assert r.json()["error"]["details"] == {"products_count": 7}
    # The delete guard's count comes from the (mocked) relation; the serializer's `products_count`
    # is a real DB annotation, covered separately in test_products_count_is_a_real_annotation.
    assert admin_client.get(f"{CATEGORIES}{c.id}/").json()["products_count"] == 0


def test_delete_with_move_children_to_root(admin_client):
    parent = CategoryFactory()
    kid = CategoryFactory(parent=parent)
    assert admin_client.delete(f"{CATEGORIES}{parent.id}/?move_children_to=root").status_code == 204
    kid.refresh_from_db()
    assert kid.parent is None and not Category.objects.filter(pk=parent.pk).exists()


def test_delete_with_move_children_to_a_category(admin_client):
    parent, target = CategoryFactory(), CategoryFactory()
    kid = CategoryFactory(parent=parent)
    assert admin_client.delete(f"{CATEGORIES}{parent.id}/?move_children_to={target.id}").status_code == 204
    kid.refresh_from_db()
    assert kid.parent == target


@pytest.mark.parametrize("value", ["abc", "-1", "1.5", ""])
def test_delete_rejects_a_malformed_move_target(admin_client, value):
    parent = CategoryFactory()
    CategoryFactory(parent=parent)
    r = admin_client.delete(f"{CATEGORIES}{parent.id}/?move_children_to={value}")
    assert r.status_code == 400 and "move_children_to" in details(r)
    assert Category.objects.count() == 2


def test_delete_rejects_a_missing_or_descendant_move_target(admin_client):
    a = CategoryFactory()
    b = CategoryFactory(parent=a)
    for target in (99999, a.id, b.id):
        r = admin_client.delete(f"{CATEGORIES}{a.id}/?move_children_to={target}")
        assert r.status_code == 400 and "move_children_to" in details(r), target
    assert Category.objects.count() == 2


def test_delete_move_target_with_clashing_names_is_a_400(admin_client):
    parent, target = CategoryFactory(), CategoryFactory()
    CategoryFactory(name="Serum", slug="s1", parent=parent)
    CategoryFactory(name="serum", slug="s2", parent=target)
    r = admin_client.delete(f"{CATEGORIES}{parent.id}/?move_children_to={target.id}")
    assert r.status_code == 400 and "move_children_to" in details(r)


def test_move_children_to_is_ignored_when_there_are_no_children(admin_client):
    c = CategoryFactory()
    assert admin_client.delete(f"{CATEGORIES}{c.id}/?move_children_to=root").status_code == 204


def test_delete_missing_category_is_404(admin_client):
    assert admin_client.delete(f"{CATEGORIES}99999/").status_code == 404


# --- images -------------------------------------------------------------------------------------------------------


def test_category_image_upload_and_validation(admin_client):
    r = admin_client.post(CATEGORIES, {"name": "With Image", "image": png("x.png")}, format="multipart")
    assert r.status_code == 201 and r.json()["image"].startswith("http://testserver/media/categories/")
    for bad in (png("x.gif", "GIF"), SimpleUploadedFile("x.png", b"<html>nope</html>")):
        r = admin_client.post(CATEGORIES, {"name": "Bad", "image": bad}, format="multipart")
        assert r.status_code == 400 and "image" in details(r)


def test_replacing_or_clearing_an_image_removes_the_old_file(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        c = admin_client.post(CATEGORIES, {"name": "Pic", "image": png("one.png")}, format="multipart").json()
    first = Category.objects.get(pk=c["id"]).image.name
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.patch(f"{CATEGORIES}{c['id']}/", {"image": png("two.png")}, format="multipart")
    second = Category.objects.get(pk=c["id"]).image.name
    assert second != first and default_storage.exists(second) and not default_storage.exists(first)
    with django_capture_on_commit_callbacks(execute=True):
        r = admin_client.patch(f"{CATEGORIES}{c['id']}/", {"image": ""}, format="multipart")
    assert r.json()["image"] is None and not default_storage.exists(second)


def test_editing_other_fields_keeps_the_image(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        c = admin_client.post(CATEGORIES, {"name": "Pic", "image": png()}, format="multipart").json()
    name = Category.objects.get(pk=c["id"]).image.name
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.patch(f"{CATEGORIES}{c['id']}/", {"description": "x"}, format="json")
    assert default_storage.exists(name)


def test_deleting_a_category_removes_its_image_file(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        c = admin_client.post(CATEGORIES, {"name": "Pic", "image": png()}, format="multipart").json()
    name = Category.objects.get(pk=c["id"]).image.name
    with django_capture_on_commit_callbacks(execute=True):
        assert admin_client.delete(f"{CATEGORIES}{c['id']}/").status_code == 204
    assert not default_storage.exists(name)


# --- brands ----------------------------------------------------------------------------------------------------------


def test_brand_crud(admin_client):
    r = admin_client.post(BRANDS, {"name": "CeraVe", "description": "Dermatologist developed"}, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "cerave" and body["is_active"] is True and set(body) == {"id", "name", "slug", "logo", "description", "is_active", "created_at", "updated_at"}
    r = admin_client.patch(f"{BRANDS}{body['id']}/", {"is_active": False, "description": "Updated"}, format="json")
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert admin_client.get(f"{BRANDS}{body['id']}/").json()["description"] == "Updated"
    assert admin_client.delete(f"{BRANDS}{body['id']}/").status_code == 204
    assert not Brand.objects.exists()


def test_brand_names_are_unique_ignoring_case(admin_client):
    BrandFactory(name="CeraVe")
    r = admin_client.post(BRANDS, {"name": "cerave"}, format="json")
    assert r.status_code == 400 and "name" in details(r)
    other = BrandFactory(name="Other")
    assert "name" in details(admin_client.patch(f"{BRANDS}{other.id}/", {"name": "CERAVE"}, format="json"))
    assert admin_client.patch(f"{BRANDS}{other.id}/", {"name": "OTHER"}, format="json").status_code == 200


def test_brand_list_includes_inactive_and_filters(admin_client):
    live, dead = BrandFactory(name="Live"), BrandFactory(name="Dead", is_active=False)
    assert admin_client.get(BRANDS).json()["count"] == 2
    assert [b["id"] for b in admin_client.get(f"{BRANDS}?is_active=false").json()["results"]] == [dead.id]
    assert [b["id"] for b in admin_client.get(f"{BRANDS}?search=liv").json()["results"]] == [live.id]
    assert [b["name"] for b in admin_client.get(f"{BRANDS}?ordering=-name").json()["results"]] == ["Live", "Dead"]


def test_brand_logo_upload_replace_and_delete(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        b = admin_client.post(BRANDS, {"name": "Logo Co", "logo": png("l.png")}, format="multipart").json()
    assert b["logo"].startswith("http://testserver/media/brands/")
    first = Brand.objects.get(pk=b["id"]).logo.name
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.patch(f"{BRANDS}{b['id']}/", {"logo": png("l2.png")}, format="multipart")
    second = Brand.objects.get(pk=b["id"]).logo.name
    assert not default_storage.exists(first) and default_storage.exists(second)
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.delete(f"{BRANDS}{b['id']}/")
    assert not default_storage.exists(second)


def test_brand_invalid_logo(admin_client):
    r = admin_client.post(BRANDS, {"name": "X", "logo": png("l.gif", "GIF")}, format="multipart")
    assert r.status_code == 400 and "logo" in details(r)


# --- tags -------------------------------------------------------------------------------------------------------------


def test_tag_crud(admin_client):
    r = admin_client.post(TAGS, {"name": "Vegan"}, format="json")
    assert r.status_code == 201 and r.json()["slug"] == "vegan" and set(r.json()) == {"id", "name", "slug", "created_at", "updated_at"}
    tid = r.json()["id"]
    assert admin_client.patch(f"{TAGS}{tid}/", {"name": "Cruelty Free"}, format="json").json()["slug"] == "cruelty-free"
    assert admin_client.get(f"{TAGS}?search=cruel").json()["count"] == 1
    assert admin_client.delete(f"{TAGS}{tid}/").status_code == 204
    assert admin_client.get(f"{TAGS}{tid}/").status_code == 404


def test_tag_names_are_unique_ignoring_case_and_required(admin_client):
    TagFactory(name="Vegan")
    assert "name" in details(admin_client.post(TAGS, {"name": "VEGAN"}, format="json"))
    assert "name" in details(admin_client.post(TAGS, {}, format="json"))
    assert "name" in details(admin_client.post(TAGS, {"name": "x" * 61}, format="json"))


def test_products_count_is_a_real_annotation_not_a_per_row_query(admin_client, django_assert_max_num_queries):
    from apps.catalog.tests.factories import ProductFactory

    category = CategoryFactory()
    products = ProductFactory.create_batch(3)
    for product in products:
        product.categories.set([category])
    with django_assert_max_num_queries(6):
        body = admin_client.get(f"{CATEGORIES}{category.id}/").json()
    assert body["products_count"] == 3
    CategoryFactory.create_batch(10)
    with django_assert_max_num_queries(6):
        admin_client.get(CATEGORIES)
