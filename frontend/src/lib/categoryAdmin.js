// Helpers over the category tree (GET /admin/categories/tree/: every category nested by `children`, ordered like
// the backend orders them). Categories nest without a depth limit (apps.catalog.models.Category.parent).

// Depth-first list of { id, name, is_active, depth }.
export function flattenCategoryTree(nodes, depth = 0, out = []) {
  for (const node of nodes ?? []) {
    out.push({ id: node.id, name: node.name, is_active: node.is_active, depth });
    flattenCategoryTree(node.children, depth + 1, out);
  }
  return out;
}

// Parent choices for a category: every category except itself and anything under it — the same loop rule the
// backend enforces (apps.catalog.services.assert_valid_parent), so the picker never offers a refused move.
export function parentOptions(nodes, excludeId = null, depth = 0, out = []) {
  for (const node of nodes ?? []) {
    if (node.id === excludeId) continue; // skips its whole subtree too
    out.push({ id: node.id, name: node.name, is_active: node.is_active, depth });
    parentOptions(node.children, excludeId, depth + 1, out);
  }
  return out;
}
