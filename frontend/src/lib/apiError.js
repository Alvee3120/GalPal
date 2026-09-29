// The first readable message anywhere in a DRF error `details` value — including nested ones such as a line item's
// error ({ items: [{ quantity: ["Only 2 left in stock."] }] }), which a flat lookup would miss.
function firstMessage(value) {
  if (typeof value === "string") return value.length <= 160 ? value : null;
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = firstMessage(item);
      if (found) return found;
    }
    return null;
  }
  if (value && typeof value === "object") return firstMessage(Object.values(value));
  return null;
}

// User-facing text for a failed API call: the backend's own validation message when it sent one
// for a 4xx (e.g. "Product not found."), otherwise the caller's friendly fallback. Never raw errors.
export function messageFor(err, fallback) {
  const detail = err.details ? firstMessage(err.details) : null;
  return err.status >= 400 && err.status < 500 && detail ? detail : fallback;
}
