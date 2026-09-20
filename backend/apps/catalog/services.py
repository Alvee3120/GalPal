"""Catalog business logic: category tree integrity, visibility, safe deletion, and products
(pricing/stock rules, variant option uniqueness, duplication)."""

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.core.utils import discard_file, unique_slugify

from .exceptions import Conflict
from .models import (
    AttributeValue,
    Category,
    Product,
    ProductCategory,
    ProductImage,
    ProductStatus,
    ProductVariant,
    StockMovement,
    StockStatus,
)

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


def parent_map():
    """Public wrapper around `_parent_map()`, for callers outside this module (e.g. filters)."""
    return _parent_map()


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


# --- products: SKU, categories, variant options -------------------------------------------


def assert_unique_sku(sku, *, exclude_product=None, exclude_variant=None):
    """
    SKUs are unique across the whole catalog (products and variants share one namespace), so a
    warehouse barcode never points at two different things. Raises a `ValidationError` on `sku`.
    """
    products = Product.all_objects.filter(sku=sku)
    if exclude_product is not None:
        products = products.exclude(pk=exclude_product.pk)
    variants = ProductVariant.objects.filter(sku=sku)
    if exclude_variant is not None:
        variants = variants.exclude(pk=exclude_variant.pk)
    if products.exists() or variants.exists():
        raise field_error("sku", "This SKU is already in use.", "duplicate_sku")


@transaction.atomic
def set_categories(product, category_ids, primary_id=None):
    """
    Replace `product`'s categories with `category_ids`, marking `primary_id` as the primary one
    (defaulting to the first id when there is at least one category and none was specified).
    """
    category_ids = list(dict.fromkeys(category_ids))  # de-duplicate, keep order
    if primary_id is not None and primary_id not in category_ids:
        raise field_error("primary_category", "The primary category must be one of the selected categories.", "invalid_primary")
    found = set(Category.objects.filter(pk__in=category_ids).values_list("pk", flat=True))
    missing = [i for i in category_ids if i not in found]
    if missing:
        raise field_error("categories", f"Unknown category id(s): {missing}.", "not_found")

    primary_id = primary_id or (category_ids[0] if category_ids else None)
    ProductCategory.objects.filter(product=product).exclude(category_id__in=category_ids).delete()
    for category_id in category_ids:
        ProductCategory.objects.update_or_create(
            product=product, category_id=category_id, defaults={"is_primary": category_id == primary_id}
        )


def option_signature(attribute_value_ids):
    return ",".join(str(i) for i in sorted(attribute_value_ids))


@transaction.atomic
def set_variant_options(variant, attribute_value_ids):
    """
    Set a variant's attribute-value combination, enforcing that no two variants of the same
    product share the same combination (the model's unique constraint is the backstop for races).
    """
    attribute_value_ids = list(dict.fromkeys(attribute_value_ids))
    found = set(AttributeValue.objects.filter(pk__in=attribute_value_ids).values_list("pk", flat=True))
    missing = [i for i in attribute_value_ids if i not in found]
    if missing:
        raise field_error("attribute_values", f"Unknown attribute value id(s): {missing}.", "not_found")

    signature = option_signature(attribute_value_ids)
    clash = ProductVariant.objects.filter(product=variant.product, option_signature=signature)
    if variant.pk is not None:
        clash = clash.exclude(pk=variant.pk)
    if clash.exists():
        raise field_error(
            "attribute_values", "Another variant of this product already uses this combination.", "duplicate_combination"
        )
    variant.option_signature = signature
    variant.save(update_fields=["option_signature"])
    variant.attribute_values.set(attribute_value_ids)


# --- products: stock -----------------------------------------------------------------------


@transaction.atomic
def adjust_stock(*, product, variant=None, quantity_change, reason, reference="", note="", user=None):
    """
    Apply `quantity_change` to a product's or a variant's stock and write a `StockMovement`.

    Locks the row so concurrent sales can't oversell. Refuses to go negative, and refuses
    altogether when stock isn't managed for the target (turn on `manage_stock` first).
    """
    target = variant or product
    model = type(target)
    locked = model.objects.select_for_update().get(pk=target.pk)
    if not locked.manage_stock:
        raise field_error("quantity_change", "Stock is not managed for this item.", "stock_not_managed")

    new_balance = locked.stock_quantity + quantity_change
    if new_balance < 0:
        raise field_error(
            "quantity_change", f"Not enough stock: only {locked.stock_quantity} on hand.", "insufficient_stock"
        )

    locked.stock_quantity = new_balance
    update_fields = ["stock_quantity"]
    if variant is None and locked.stock_status != StockStatus.BACKORDER:
        locked.stock_status = StockStatus.IN_STOCK if new_balance > 0 else StockStatus.OUT_OF_STOCK
        update_fields.append("stock_status")
    locked.save(update_fields=update_fields)

    movement = StockMovement.objects.create(
        product=variant.product if variant else product,
        variant=variant,
        quantity_change=quantity_change,
        balance_after=new_balance,
        reason=reason,
        reference=reference,
        note=note,
        user=user,
    )
    return locked, movement


# --- products: bulk actions & duplication ---------------------------------------------------


@transaction.atomic
def bulk_set_status(product_ids, status):
    updated = Product.objects.filter(pk__in=product_ids).update(status=status, updated_at=timezone.now())
    return updated


def _copy_image(field_file):
    """A new, independent copy of an uploaded image file (so duplicates never share storage)."""
    if not field_file:
        return None
    field_file.open("rb")
    try:
        return ContentFile(field_file.read(), name=field_file.name.rsplit("/", 1)[-1])
    finally:
        field_file.close()


def _unique_sku(base):
    candidate, counter = f"{base}-copy", 1
    while Product.all_objects.filter(sku=candidate).exists() or ProductVariant.objects.filter(sku=candidate).exists():
        counter += 1
        candidate = f"{base}-copy-{counter}"
    return candidate


_COPY_EXCLUDED = {
    "id", "name", "slug", "sku", "stock_quantity", "average_rating", "review_count", "status",
    "created_at", "updated_at", "is_deleted", "deleted_at", "feature_image", "og_image",
}


@transaction.atomic
def duplicate_product(product):
    """
    Deep-copy a product: scalar fields, categories, tags, gallery images and variants (each with
    an independent copy of its image file). The duplicate is always a draft with zero stock, a
    fresh SKU (`<sku>-copy`, de-duplicated) and no rating/review history, ready for the admin to
    finish and publish.
    """
    fields = {
        f.attname: getattr(product, f.attname)
        for f in Product._meta.concrete_fields
        if f.name not in _COPY_EXCLUDED
    }
    copy = Product(
        **fields,
        name=f"{product.name} (Copy)",
        slug=unique_slugify(Product, f"{product.name} (Copy)"),
        sku=_unique_sku(product.sku),
        status=ProductStatus.DRAFT,
        stock_quantity=0,
        feature_image=_copy_image(product.feature_image),
        og_image=_copy_image(product.og_image),
    )
    copy.save()

    copy.tags.set(product.tags.all())
    for link in product.category_links.all():
        ProductCategory.objects.create(product=copy, category_id=link.category_id, is_primary=link.is_primary)

    for image in product.images.all():
        copied = _copy_image(image.image)
        if copied:
            ProductImage.objects.create(product=copy, image=copied, alt_text=image.alt_text, sort_order=image.sort_order)

    for variant in product.variants.all():
        new_variant = ProductVariant.objects.create(
            product=copy,
            option_signature=variant.option_signature,
            sku=_unique_sku(variant.sku),
            regular_price=variant.regular_price,
            discount_price=variant.discount_price,
            stock_quantity=0,
            manage_stock=variant.manage_stock,
            is_active=variant.is_active,
            image=_copy_image(variant.image),
        )
        new_variant.attribute_values.set(variant.attribute_values.all())

    return copy
