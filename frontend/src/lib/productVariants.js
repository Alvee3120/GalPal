// Groups every variant's attribute_values by attribute, e.g. { id, name: "Shade", values: [{id, value}, ...] } —
// the same grouping the customer-facing Product Details page uses (component/product/ProductDetailContent.jsx),
// extracted here so the CCE order product picker (which needs the identical variant-selection UI) imports the
// same function instead of a second copy.
export function buildAttributeGroups(variants) {
  const groups = new Map();
  for (const variant of variants) {
    for (const av of variant.attribute_values) {
      if (!groups.has(av.attribute_id)) groups.set(av.attribute_id, { id: av.attribute_id, name: av.attribute, values: new Map() });
      groups.get(av.attribute_id).values.set(av.id, av.value);
    }
  }
  return [...groups.values()].map((g) => ({ ...g, values: [...g.values.entries()].map(([id, value]) => ({ id, value })) }));
}

// "Shade: Medium / Size: 30ml" — mirrors the backend's own apps.orders.services._variant_label() formatting
// exactly (same " / " join, same "Attribute: Value" shape, same attribute-name-then-value ordering), so a variant
// picked here displays identically to how the backend will label it once persisted on the order item.
export function variantLabel(variant) {
  if (!variant) return "";
  return [...variant.attribute_values]
    .sort((a, b) => a.attribute.localeCompare(b.attribute) || a.value.localeCompare(b.value))
    .map((av) => `${av.attribute}: ${av.value}`)
    .join(" / ");
}
