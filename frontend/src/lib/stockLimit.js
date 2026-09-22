// The ONE place "how many more of this can go in the cart" is worked out — used by the product card, the product
// detail page's quantity stepper, and the cart drawer/page's quantity stepper, so none of them can drift out of
// sync with each other or with the backend's own rule (apps.cart.services.available_quantity: unmanaged stock is
// uncapped, everything else caps at stock_quantity). The backend is still the final authority on every write
// (add/set-quantity/checkout all re-validate server-side) — this only drives the UI so a customer is stopped
// before they submit something that would be rejected anyway.

// A product or variant's own stock cap, or null for "no cap" (manage_stock is off). Give it the product, or the
// selected variant when the product has one — both carry the same `stock_quantity`/`manage_stock` shape.
export function getStockCap(source) {
  if (!source || source.manage_stock === false) return null;
  return typeof source.stock_quantity === "number" ? source.stock_quantity : null;
}

// How many of this exact product/variant are already sitting in the cart.
export function quantityInCart(items, productId, variantId = null) {
  const line = items.find((item) => item.product.id === productId && (item.variant?.id ?? null) === (variantId ?? null));
  return line?.quantity ?? 0;
}

// How many more can be added right now (Infinity when uncapped).
export function remainingToAdd(cap, alreadyInCart) {
  return cap === null ? Infinity : Math.max(0, cap - alreadyInCart);
}

// For a line ALREADY in the cart: the backend computes its exact remaining room per line (CartItemSerializer's
// `available_quantity` — accounts for the real product/variant, manage_stock, and backorder all at once), so the
// cart drawer/page read that instead of recomputing it from raw product fields.
export function isAtCartLimit(item) {
  return typeof item.available_quantity === "number" && item.quantity >= item.available_quantity;
}

// A cart line's own unavailability message — `item.is_available` is set by the backend's live check
// (apps.cart.services.summarize/line_price), covering both "no longer buyable at all" (deactivated variant,
// unpublished product) and "not enough left for the quantity in the cart". Returns null when the line is fine.
export function cartLineIssue(item) {
  if (item.is_available !== false) return null;
  if (item.available_quantity === 0) return "Out of Stock";
  if (typeof item.available_quantity === "number" && item.available_quantity > 0) return `Only ${item.available_quantity} available`;
  return "No longer available";
}
