import re

import pytest
from django.db import connection, models

from apps.core.utils import UploadPath, unique_slugify


class Widget(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=20, unique=True)

    class Meta:
        app_label = "core"


@pytest.fixture
def widget_table(db):
    # Postgres DDL is transactional: the table vanishes when the test's transaction rolls back.
    with connection.schema_editor() as editor:
        editor.create_model(Widget)


def test_basic_slug(widget_table):
    assert unique_slugify(Widget, "Vitamin C Serum") == "vitamin-c-serum"


def test_collisions_get_numeric_suffix(widget_table):
    Widget.objects.create(name="a", slug="serum")
    assert unique_slugify(Widget, "Serum") == "serum-2"
    Widget.objects.create(name="b", slug="serum-2")
    assert unique_slugify(Widget, "Serum") == "serum-3"


def test_instance_does_not_collide_with_itself(widget_table):
    widget = Widget.objects.create(name="a", slug="serum")
    assert unique_slugify(Widget, "Serum", instance=widget) == "serum"


def test_suffix_respects_max_length(widget_table):
    long_name = "x" * 40
    Widget.objects.create(name="a", slug="x" * 20)
    slug = unique_slugify(Widget, long_name)
    assert len(slug) <= 20 and slug.endswith("-2")


def test_bangla_is_transliterated_not_dropped(widget_table):
    slug = unique_slugify(Widget, "ফেস ওয়াশ")
    assert re.fullmatch(r"[a-z0-9-]+", slug) and slug != "item"


def test_unsluggable_input_uses_fallback(widget_table):
    assert unique_slugify(Widget, "!!!") == "item"
    assert unique_slugify(Widget, "", fallback="brand") == "brand"


def test_upload_path_is_organised_and_random():
    upload_to = UploadPath("products/")
    path = upload_to(None, "My Photo (1).JPG")
    assert re.fullmatch(r"products/\d{4}/\d{2}/[0-9a-f]{32}\.jpg", path)
    assert upload_to(None, "My Photo (1).JPG") != path


def test_upload_path_is_migration_serializable():
    assert UploadPath("banners").deconstruct()[1] == ("banners",)


def test_reserved_slugs_are_treated_as_taken(widget_table):
    assert unique_slugify(Widget, "Tree", reserved={"tree"}) == "tree-2"
    assert unique_slugify(Widget, "Tree", reserved={"tree", "tree-2"}) == "tree-3"
    assert unique_slugify(Widget, "Tree") == "tree"
    Widget.objects.create(name="a", slug="tree-2")
    assert unique_slugify(Widget, "Tree", reserved={"tree"}) == "tree-3"
