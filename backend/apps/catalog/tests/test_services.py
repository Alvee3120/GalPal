import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.catalog import services
from apps.catalog.exceptions import Conflict
from apps.catalog.models import Category

from .factories import CategoryFactory

pytestmark = pytest.mark.django_db


def code_of(exc, field):
    return exc.value.error_dict[field][0].code


def chain(depth):
    """root -> ... a straight line of `depth` categories, returned root first."""
    nodes, parent = [], None
    for _ in range(depth):
        parent = CategoryFactory(parent=parent)
        nodes.append(parent)
    return nodes


# --- circular parent protection ----------------------------------------------------------------


def test_no_parent_or_unrelated_parent_is_valid():
    a, b = CategoryFactory(), CategoryFactory()
    services.assert_valid_parent(a, None)
    services.assert_valid_parent(a, b)
    services.assert_valid_parent(None, b)  # creating


def test_own_parent_is_rejected():
    a = CategoryFactory()
    with pytest.raises(ValidationError) as exc:
        services.assert_valid_parent(a, a)
    assert code_of(exc, "parent") == "self_parent" and "parent" in exc.value.message_dict


def test_child_as_parent_is_rejected():
    parent, child = chain(2)
    with pytest.raises(ValidationError) as exc:
        services.assert_valid_parent(parent, child)
    assert code_of(exc, "parent") == "circular_parent"


def test_deep_descendant_as_parent_is_rejected():
    nodes = chain(25)
    with pytest.raises(ValidationError):
        services.assert_valid_parent(nodes[0], nodes[-1])
    services.assert_valid_parent(nodes[-1], nodes[0])  # moving up is fine
    services.assert_valid_parent(nodes[5], CategoryFactory())  # moving to another tree is fine


def test_a_corrupt_cycle_in_existing_data_does_not_hang():
    a, b = chain(2)
    Category.objects.filter(pk=a.pk).update(parent=b)  # force a loop behind the app's back
    c = CategoryFactory()
    services.assert_valid_parent(c, a)  # must terminate
    assert services._ancestor_ids(a.pk, services._parent_map()) == [a.pk, b.pk]


def test_descendant_ids():
    root, mid, leaf = chain(3)
    other = CategoryFactory()
    pm = services._parent_map()
    assert services.descendant_ids(root.pk, pm) == {mid.pk, leaf.pk}
    assert services.descendant_ids(leaf.pk, pm) == set() and services.descendant_ids(other.pk, pm) == set()


# --- visibility index --------------------------------------------------------------------------


def test_visible_means_active_with_all_ancestors_active():
    root = CategoryFactory()
    hidden = CategoryFactory(parent=root, is_active=False)
    under_hidden = CategoryFactory(parent=hidden)
    deeper = CategoryFactory(parent=under_hidden)
    sibling = CategoryFactory(parent=root)
    inactive_root = CategoryFactory(is_active=False)
    under_inactive_root = CategoryFactory(parent=inactive_root)
    visible = services.CategoryIndex().visible_ids()
    assert visible == {root.pk, sibling.pk}
    assert not {hidden.pk, under_hidden.pk, deeper.pk, inactive_root.pk, under_inactive_root.pk} & visible


def test_visibility_of_a_very_deep_tree_needs_no_recursion():
    nodes = chain(1500)  # deeper than Python's default recursion limit
    assert len(services.CategoryIndex().visible_ids()) == 1500
    Category.objects.filter(pk=nodes[3].pk).update(is_active=False)
    assert len(services.CategoryIndex().visible_ids()) == 3


def test_index_uses_one_query(django_assert_num_queries):
    chain(10)
    with django_assert_num_queries(1):
        index = services.CategoryIndex()
        index.visible_ids(); index.breadcrumb(1); index.children(1)


def test_breadcrumb_runs_root_to_category():
    root, mid, leaf = chain(3)
    index = services.CategoryIndex()
    assert [c["id"] for c in index.breadcrumb(leaf.pk)] == [root.pk, mid.pk, leaf.pk]
    assert index.breadcrumb(root.pk) == [{"id": root.pk, "name": root.name, "slug": root.slug}]


def test_children_are_visible_direct_children_in_display_order():
    root = CategoryFactory()
    b = CategoryFactory(parent=root, name="B", sort_order=2)
    a = CategoryFactory(parent=root, name="A", sort_order=1)
    CategoryFactory(parent=root, is_active=False)
    CategoryFactory(parent=a)  # grandchild: not a direct child
    assert [c["id"] for c in services.CategoryIndex().children(root.pk)] == [a.pk, b.pk]


# --- tree building -----------------------------------------------------------------------------


def test_build_tree_nests_and_keeps_order():
    r2 = CategoryFactory(name="R2", sort_order=2)
    r1 = CategoryFactory(name="R1", sort_order=1)
    c2 = CategoryFactory(name="C2", parent=r1, sort_order=2)
    c1 = CategoryFactory(name="C1", parent=r1, sort_order=1)
    g = CategoryFactory(name="G", parent=c1)
    cats = list(Category.objects.order_by("sort_order", "name"))
    tree = services.build_tree(cats, lambda c: {"id": c.pk, "name": c.name})
    assert [n["name"] for n in tree] == ["R1", "R2"]
    assert [n["name"] for n in tree[0]["children"]] == ["C1", "C2"]
    assert tree[0]["children"][0]["children"] == [{"id": g.pk, "name": "G", "children": []}]
    assert tree[1]["children"] == [] and r2 and c2


def test_build_tree_orphans_become_roots_when_the_parent_is_filtered_out():
    root, child = chain(2)
    tree = services.build_tree([child], lambda c: {"id": c.pk})
    assert [n["id"] for n in tree] == [child.pk] and root


def test_build_tree_handles_very_deep_trees():
    chain(1200)
    cats = list(Category.objects.order_by("id"))
    tree = services.build_tree(cats, lambda c: {"id": c.pk})
    assert len(tree) == 1 and len(tree[0]["children"]) == 1


# --- delete ------------------------------------------------------------------------------------


def test_a_leaf_category_is_deleted():
    category = CategoryFactory()
    services.delete_category(category)
    assert not Category.objects.filter(pk=category.pk).exists()


def test_children_block_deletion_with_counts():
    parent = CategoryFactory()
    CategoryFactory.create_batch(2, parent=parent)
    with pytest.raises(Conflict) as exc:
        services.delete_category(parent)
    assert exc.value.get_codes() == "category_has_children" and exc.value.details == {"children_count": 2}
    assert Category.objects.count() == 3


def test_products_block_deletion_even_when_children_could_be_moved(monkeypatch):
    class Products:
        def count(self):
            return 5

    monkeypatch.setattr(Category, "products", property(lambda self: Products()), raising=False)
    category = CategoryFactory()
    with pytest.raises(Conflict) as exc:
        services.delete_category(category)
    assert exc.value.get_codes() == "category_has_products" and exc.value.details == {"products_count": 5}
    CategoryFactory(parent=category)
    with pytest.raises(Conflict) as exc:
        services.delete_category(category, move_children_to=services.ROOT)
    assert exc.value.get_codes() == "category_has_products"
    assert Category.objects.count() == 2


def test_children_can_be_moved_to_the_top_level():
    parent = CategoryFactory()
    kids = CategoryFactory.create_batch(2, parent=parent)
    services.delete_category(parent, move_children_to=services.ROOT)
    assert not Category.objects.filter(pk=parent.pk).exists()
    for kid in kids:
        kid.refresh_from_db()
        assert kid.parent is None


def test_children_can_be_moved_to_another_category():
    grand, parent, other = CategoryFactory(), CategoryFactory(), CategoryFactory()
    Category.objects.filter(pk=parent.pk).update(parent=grand)
    kid = CategoryFactory(parent=parent)
    services.delete_category(parent, move_children_to=other.pk)
    kid.refresh_from_db()
    assert kid.parent == other and Category.objects.filter(pk=grand.pk).exists()


def test_children_can_move_to_the_deleted_categorys_own_parent():
    grand = CategoryFactory()
    parent = CategoryFactory(parent=grand)
    kid = CategoryFactory(parent=parent)
    services.delete_category(parent, move_children_to=grand.pk)
    kid.refresh_from_db()
    assert kid.parent == grand


def test_bad_move_targets_are_rejected_and_nothing_is_deleted():
    root, mid, leaf = chain(3)
    for target, code in [(root.pk, "invalid_target"), (leaf.pk, "invalid_target"), (999999, "not_found")]:
        with pytest.raises(ValidationError) as exc:
            services.delete_category(root, move_children_to=target)
        assert code_of(exc, "move_children_to") == code
    assert Category.objects.count() == 3 and mid


def test_move_is_refused_when_names_would_clash_at_the_target():
    parent, target = CategoryFactory(), CategoryFactory()
    CategoryFactory(name="Serum", slug="a-serum", parent=parent)
    CategoryFactory(name="serum", slug="b-serum", parent=target)
    with pytest.raises(ValidationError) as exc:
        services.delete_category(parent, move_children_to=target.pk)
    assert code_of(exc, "move_children_to") == "name_clash"
    assert Category.objects.count() == 4  # nothing moved, nothing deleted


def test_top_level_name_clash_when_moving_to_root():
    parent = CategoryFactory()
    CategoryFactory(name="Serum", slug="a", parent=parent)
    CategoryFactory(name="serum", slug="b")
    with pytest.raises(ValidationError):
        services.delete_category(parent, move_children_to=services.ROOT)


def test_deleting_removes_the_image_file_after_commit(django_capture_on_commit_callbacks):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, format="PNG")
    category = CategoryFactory(image=SimpleUploadedFile("c.png", buffer.getvalue()))
    name = category.image.name
    assert default_storage.exists(name)
    with django_capture_on_commit_callbacks(execute=True):
        services.delete_category(category)
    assert not default_storage.exists(name)
