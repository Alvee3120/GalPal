// "Shade: Rose" style summary of a cart line's variant, if it has one. Shared by the cart drawer and the
// full cart page so both describe a line's variant identically.
export function variantLabel(variant) {
  const values = variant?.attribute_values;
  if (!Array.isArray(values) || values.length === 0) return "";
  return values.map((v) => (typeof v === "string" ? v : `${v.attribute}: ${v.value}`)).join(", ");
}
