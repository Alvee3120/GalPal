"""Catalog business logic: category tree integrity, visibility, and safe deletion."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.utils import discard_file

from .exceptions import Conflict
from .models import Category

ROOT = "root"  # `move_children_to=root` re-parents children to the top level


def field_error(field, message, code):
    """A `ValidationError` on one field whose `code` survives (dict-form errors drop a top-level code)."""
    return ValidationError({field: ValidationError(message, code=code)})


# --- tree integrity ---------------------------------------------------------------------


def _parent_map(lock=False):
    """{category_id: parent_id} for every category. With `lock`, rows are locked (FOR UPDATE)."""
    queryset = Category.objects.select_for_update() if lock else Category.objects.all()
    return dict(queryset.order_by("pk").values_list("id", "parent_id"))


def _ancestor_ids(node_id, parent_map):
    """Ids from `node_id` up to the root, starting with `node_id` itself. Cycle-safe."""
    chain, seen = [], set()
    while node_id is not None and node_id not in seen:
        seen.add(node_id)
        chain.append(node_id)
        node_id = parent_map.get(node_id)
    return chain


def descendant_ids(category_id, parent_map):
    """All ids below `category_id` (children, grandchildren, ...), not including itself."""
    children = {}
    for child, parent in parent_map.items():
        children.setdefault(parent, []).append(child)
    found, stack = set(), list(children.get(category_id, []))
    while stack:
        current = stack.pop()
        if current not in found:
            found.add(current)
            stack.extend(children.get(current, []))
    return found


def assert_valid_parent(category, new_parent, *, lock=False):
    """
    Raise a `ValidationError` on `parent` if making `new_parent` the parent of `category` would
    create a cycle (a category as its own ancestor). `category` may be None (creating).

    Call with `lock=True` inside a transaction right before saving: it locks the category table
    so two concurrent moves can't each look valid and together form a loop.
    """
    if new_parent is None or category is None or category.pk is None:
        return
    if new_parent.pk == category.pk:
        raise field_error("parent", "A category cannot be its own parent.", "self_parent")
    if category.pk in _ancestor_ids(new_parent.pk, _parent_map(lock=lock)):
        raise field_error("parent", "A category cannot be moved under one of its own descendants.", "circular_parent")


# --- public visibility ------------------------------------------------------------------


class CategoryIndex:
    """
    One light query over the whole (small) category table, answering the questions the public
    API needs without a query per row: which categories are visible, a category's breadcrumb,
    and its visible children.

    Visible = active, and every ancestor active too (hiding a category hides its subtree).
    """

    def __init__(self):
        rows = Category.objects.order_by("sort_order", "name").values("id", "parent_id", "is_active", "name", "slug")
        self.rows = {row["id"]: row for row in rows}
        self._visible = None

    def visible_ids(self):
        if self._visible is None:
            memo = {}

            def visible(node_id):
                # iterative walk up with memoisation: no recursion limit for deep trees
                path = []
                while node_id is not None and node_id not in memo:
                    row = self.rows.get(node_id)
                    if row is None or not row["is_active"]:
                        memo[node_id] = False
                        break
                    path.append(node_id)
                    node_id = row["parent_id"]
                result = memo.get(node_id, True) if node_id is not None else True
                for seen in path:
                    memo[seen] = result
                return result

            self._visible = {node_id for node_id in self.rows if visible(node_id)}
        return self._visible

    def breadcrumb(self, category_id):
        """Root-to-category list of {id, name, slug}, including the category itself."""
        chain = _ancestor_ids(category_id, {i: r["parent_id"] for i, r in self.rows.items()})
        return [
            {"id": i, "name": self.rows[i]["name"], "slug": self.rows[i]["slug"]} for i in reversed(chain) if i in self.rows
        ]

    def children(self, category_id):
        """Visible direct children as {id, name, slug}, in display order."""
        visible = self.visible_ids()
        return [
            {"id": i, "name": r["name"], "slug": r["slug"]}
            for i, r in self.rows.items()
            if r["parent_id"] == category_id and i in visible
        ]


def build_tree(categories, represent):
    """
    Nest `categories` (already filtered and ordered) into a list of root nodes.

    `represent(category)` returns the node's dict; each node gets a `children` list. A category
    whose parent is not in `categories` becomes a root. One pass, no recursion, no extra queries.
    """
    nodes, roots = {}, []
    for category in categories:
        node = dict(represent(category))
        node["children"] = []
        nodes[category.pk] = node
    for category in categories:
        parent = nodes.get(category.parent_id)
        (parent["children"] if parent is not None else roots).append(nodes[category.pk])
    return roots


# --- deletion ---------------------------------------------------------------------------


@transaction.atomic
def delete_category(category, *, move_children_to=None):
    """
    Delete a category safely.

    * It has products        -> refused (409 `category_has_products`); deactivate it instead.
    * It has child categories-> refused (409 `category_has_children`) unless `move_children_to`
      is given: `ROOT` (children become top-level) or the id of another category.
    * Otherwise deleted, and its image file removed after commit.
    """
    parent_map = _parent_map(lock=True)

    products = category.product_count()
    if products:
        raise Conflict(
            f"This category has {products} product(s). Move them to another category or deactivate this one.",
            code="category_has_products",
            details={"products_count": products},
        )

    children = list(category.children.all())
    if children:
        if move_children_to is None:
            raise Conflict(
                f"This category has {len(children)} sub-categor{'y' if len(children) == 1 else 'ies'}. "
                "Delete or move them first, or pass ?move_children_to=<category id>|root to re-parent them.",
                code="category_has_children",
                details={"children_count": len(children)},
            )
        target = None
        if move_children_to != ROOT:
            target = Category.objects.filter(pk=move_children_to).first()
            if target is None:
                raise field_error("move_children_to", "Category not found.", "not_found")
            if target.pk == category.pk or target.pk in descendant_ids(category.pk, parent_map):
                raise field_error(
                    "move_children_to", "Choose a category outside the one being deleted.", "invalid_target"
                )
        _reparent_children(category, children, target)

    image = category.image
    category.delete()
    discard_file(image)


def _reparent_children(category, children, target):
    target_id = target.pk if target else None
    taken = {
        name.lower()
        for name in Category.objects.filter(parent_id=target_id).exclude(pk=category.pk).values_list("name", flat=True)
    }
    clashes = sorted(child.name for child in children if child.name.lower() in taken)
    if clashes:
        raise field_error(
            "move_children_to", f"The target already has a category named: {', '.join(clashes)}.", "name_clash"
        )
    Category.objects.filter(parent=category).update(parent=target, updated_at=timezone.now())
