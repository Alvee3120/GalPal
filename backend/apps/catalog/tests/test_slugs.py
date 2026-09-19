"""Slug rules from the spec, exercised through the admin API (Tag/Brand/Category share them)."""
import re

import pytest

from apps.catalog.models import Brand, Category, Tag

from .factories import CategoryFactory, TagFactory

pytestmark = pytest.mark.django_db

TAGS = "/api/v1/admin/tags/"
BRANDS = "/api/v1/admin/brands/"
CATEGORIES = "/api/v1/admin/categories/"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


def create(client, url, **data):
    return client.post(url, data, format="json")


# --- generated on create --------------------------------------------------------------------------


def test_slug_is_generated_from_the_name(admin_client):
    r = create(admin_client, TAGS, name="Vitamin C Serum")
    assert r.status_code == 201 and r.json()["slug"] == "vitamin-c-serum"
    assert Tag.objects.get().slug_is_custom is False


def test_collisions_get_numeric_suffixes(admin_client):
    slugs = [create(admin_client, TAGS, name=name).json()["slug"] for name in ["Glow", "glow!", "GLOW?"]]
    # names collide case-insensitively only if identical letters: "glow!" is a different name
    assert slugs == ["glow", "glow-2", "glow-3"]


def test_bangla_names_get_a_usable_slug(admin_client):
    r = create(admin_client, BRANDS, name="ফেস ওয়াশ")
    assert r.status_code == 201 and re.fullmatch(r"[a-z0-9-]+", r.json()["slug"]) and r.json()["slug"] != "item"


def test_name_with_no_sluggable_characters_falls_back(admin_client):
    r = create(admin_client, TAGS, name="!!!")
    assert r.status_code == 201 and r.json()["slug"] == "item"
    assert create(admin_client, TAGS, name="???").json()["slug"] == "item-2"


def test_generated_slug_skips_slugs_already_taken_by_other_rows(admin_client):
    TagFactory(name="Other", slug="cleanser")
    assert create(admin_client, TAGS, name="Cleanser").json()["slug"] == "cleanser-2"


# --- explicit slugs ----------------------------------------------------------------------------------


def test_admin_can_set_the_slug_on_create(admin_client):
    r = create(admin_client, TAGS, name="Vitamin C", slug="vit-c")
    assert r.json()["slug"] == "vit-c" and Tag.objects.get().slug_is_custom is True


def test_explicit_slug_is_normalised(admin_client):
    assert create(admin_client, TAGS, name="A", slug="  Face Wash!! 2  ").json()["slug"] == "face-wash-2"


def test_explicit_duplicate_slug_is_an_error_not_a_silent_suffix(admin_client):
    TagFactory(name="Taken", slug="taken")
    r = create(admin_client, TAGS, name="Different", slug="taken")
    assert r.status_code == 400 and r.json()["error"]["details"] == {"slug": ["This slug is already in use."]}
    assert Tag.objects.count() == 1


def test_explicit_slug_that_normalises_to_nothing_is_rejected(admin_client):
    r = create(admin_client, TAGS, name="A", slug="!!!")
    assert r.status_code == 400 and "slug" in r.json()["error"]["details"]


def test_blank_slug_on_create_means_automatic(admin_client):
    r = create(admin_client, TAGS, name="Hello World", slug="")
    assert r.json()["slug"] == "hello-world" and Tag.objects.get().slug_is_custom is False


# --- rename behaviour --------------------------------------------------------------------------------


def test_renaming_regenerates_an_automatic_slug(admin_client):
    tag = create(admin_client, TAGS, name="Old Name").json()
    r = admin_client.patch(f"{TAGS}{tag['id']}/", {"name": "Brand New Name"}, format="json")
    assert r.json()["slug"] == "brand-new-name"


def test_renaming_keeps_a_slug_the_admin_set_by_hand(admin_client):
    tag = create(admin_client, TAGS, name="Old Name", slug="my-own").json()
    r = admin_client.patch(f"{TAGS}{tag['id']}/", {"name": "Brand New Name"}, format="json")
    assert r.json()["slug"] == "my-own"


def test_editing_the_slug_marks_it_custom_so_later_renames_keep_it(admin_client):
    tag = create(admin_client, TAGS, name="Old Name").json()
    admin_client.patch(f"{TAGS}{tag['id']}/", {"slug": "hand-picked"}, format="json")
    assert Tag.objects.get().slug_is_custom is True
    r = admin_client.patch(f"{TAGS}{tag['id']}/", {"name": "Another"}, format="json")
    assert r.json()["slug"] == "hand-picked"


def test_form_style_resubmit_of_the_unchanged_slug_still_regenerates_an_automatic_slug(admin_client):
    """An admin form sends every field back; an untouched slug must not count as 'set by hand'."""
    tag = create(admin_client, TAGS, name="Old Name").json()
    r = admin_client.patch(f"{TAGS}{tag['id']}/", {"name": "Fresh Name", "slug": tag["slug"]}, format="json")
    assert r.json()["slug"] == "fresh-name" and Tag.objects.get().slug_is_custom is False


def test_form_style_resubmit_keeps_a_custom_slug(admin_client):
    tag = create(admin_client, TAGS, name="Old Name", slug="mine").json()
    r = admin_client.patch(f"{TAGS}{tag['id']}/", {"name": "Fresh Name", "slug": "mine"}, format="json")
    assert r.json()["slug"] == "mine"


def test_blank_slug_on_update_switches_back_to_automatic(admin_client):
    tag = create(admin_client, TAGS, name="Some Name", slug="custom").json()
    r = admin_client.patch(f"{TAGS}{tag['id']}/", {"slug": ""}, format="json")
    assert r.json()["slug"] == "some-name" and Tag.objects.get().slug_is_custom is False
    # ...and renaming now regenerates again
    assert admin_client.patch(f"{TAGS}{tag['id']}/", {"name": "Renamed"}, format="json").json()["slug"] == "renamed"


def test_editing_something_else_never_touches_the_slug(admin_client):
    brand = create(admin_client, BRANDS, name="CeraVe").json()
    r = admin_client.patch(f"{BRANDS}{brand['id']}/", {"description": "Derm-developed"}, format="json")
    assert r.json()["slug"] == "cerave"


def test_regenerated_slug_does_not_collide_with_itself_or_others(admin_client):
    TagFactory(name="Taken", slug="fresh")
    tag = create(admin_client, TAGS, name="Original").json()
    r = admin_client.patch(f"{TAGS}{tag['id']}/", {"name": "Fresh"}, format="json")
    assert r.json()["slug"] == "fresh-2"
    # renaming to something that slugifies to its own slug keeps it (no "-2" against itself)
    assert admin_client.patch(f"{TAGS}{tag['id']}/", {"name": "Fresh!"}, format="json").json()["slug"] == "fresh-2"


def test_taking_another_rows_slug_by_hand_on_update_is_rejected(admin_client):
    TagFactory(name="First", slug="first")
    second = create(admin_client, TAGS, name="Second").json()
    r = admin_client.patch(f"{TAGS}{second['id']}/", {"slug": "first"}, format="json")
    assert r.status_code == 400 and "slug" in r.json()["error"]["details"]
    assert Tag.objects.get(pk=second["id"]).slug == "second"


def test_same_rules_apply_to_brands_and_categories(admin_client):
    brand = create(admin_client, BRANDS, name="La Roche-Posay").json()
    assert brand["slug"] == "la-roche-posay"
    cat = create(admin_client, CATEGORIES, name="Sun Care").json()
    assert cat["slug"] == "sun-care"
    r = admin_client.patch(f"{CATEGORIES}{cat['id']}/", {"name": "Sunscreen"}, format="json")
    assert r.json()["slug"] == "sunscreen"


# --- reserved slugs (a category named "Tree" would shadow /categories/tree/) ----------------------------


def test_a_category_named_tree_does_not_take_the_reserved_slug(admin_client):
    r = create(admin_client, CATEGORIES, name="Tree")
    assert r.status_code == 201 and r.json()["slug"] == "tree-2"


def test_reserved_slug_cannot_be_set_by_hand(admin_client):
    r = create(admin_client, CATEGORIES, name="Anything", slug="tree")
    assert r.status_code == 400 and "slug" in r.json()["error"]["details"]


def test_other_models_may_use_the_word_tree(admin_client):
    assert create(admin_client, TAGS, name="Tree").json()["slug"] == "tree"


def test_the_reserved_category_route_still_works(api_client):
    CategoryFactory(name="Tree Care", slug="tree-care")
    assert api_client.get("/api/v1/categories/tree/").status_code == 200


# --- races ----------------------------------------------------------------------------------------------


def test_losing_a_slug_race_is_a_400_not_a_500(admin_client, monkeypatch):
    """Two requests pick the same free slug; the DB unique constraint rejects the loser."""
    TagFactory(name="Winner", slug="race")
    monkeypatch.setattr("apps.core.serializers.resolve_slug", lambda *a, **k: ("race", False))
    r = create(admin_client, TAGS, name="Loser")
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"
    assert Tag.objects.count() == 1


def test_slug_field_is_never_left_empty(admin_client):
    for url in (TAGS, BRANDS, CATEGORIES):
        assert create(admin_client, url, name="X Y").json()["slug"] == "x-y"
    assert Brand.objects.get().slug and Category.objects.get().slug
