// Discount Management constants, mirroring apps.discounts.models (DiscountKind / DiscountTarget / DiscountStatus). The
// backend validates every value and works out every price; these only drive the controls. Cart-offer kinds are worked
// out by the backend over the whole cart (apps.discounts.promotions) — the frontend never computes a discount itself.
export const DISCOUNT_KINDS = [
  { value: "percentage", label: "Percentage", group: "price" },
  { value: "fixed", label: "Fixed amount", group: "price" },
  { value: "buy_x_get_y_percent", label: "Buy X items, get Y% off", group: "cart" },
  { value: "buy_x_get_y_free", label: "Buy X, get Y free", group: "cart" },
  { value: "lowest_free", label: "Buy X, get the lowest-priced item free", group: "cart" },
  { value: "three_for_two", label: "3 for 2", group: "cart" },
  { value: "bundle_price", label: "Buy X products for a fixed price", group: "cart" },
];
export const DISCOUNT_KIND_LABEL = Object.fromEntries(DISCOUNT_KINDS.map((k) => [k.value, k.label]));

// Which configuration fields each kind shows in the form (and sends). Product kinds use `value`; 3 for 2 is fixed at
// 3 buy / 1 free; the rest pick the relevant quantities.
export const DISCOUNT_KIND_FIELDS = {
  percentage: {},
  fixed: {},
  buy_x_get_y_percent: { minQuantity: true, percentOff: true, allowRepeat: true },
  buy_x_get_y_free: { minQuantity: true, freeQuantity: true, sameProductGroup: true, allowRepeat: true },
  lowest_free: { minQuantity: true, allowRepeat: true },
  three_for_two: { sameProductGroup: true, allowRepeat: true },
  bundle_price: { minQuantity: true, bundlePrice: true, allowRepeat: true },
};

export const DISCOUNT_TARGETS = [
  { value: "category", label: "Category" },
  { value: "products", label: "Specific products" },
];
export const DISCOUNT_TARGET_LABEL = Object.fromEntries(DISCOUNT_TARGETS.map((t) => [t.value, t.label]));

export const DISCOUNT_STATUSES = [
  { value: "active", label: "Active" },
  { value: "scheduled", label: "Scheduled" },
  { value: "expired", label: "Expired" },
  { value: "inactive", label: "Inactive" },
];
export const DISCOUNT_STATUS_LABEL = Object.fromEntries(DISCOUNT_STATUSES.map((s) => [s.value, s.label]));

export const isProductKind = (kind) => kind === "percentage" || kind === "fixed";

export async function discountFetch(path = "", { method = "GET", body } = {}) {
  try {
    const res = await fetch(`/api/admin/discounts${path}`, {
      method,
      cache: "no-store",
      body: body === undefined ? undefined : JSON.stringify(body),
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    });
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, data };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}
