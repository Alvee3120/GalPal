// Discount Management constants, mirroring apps.discounts.models (DiscountKind / DiscountTarget / DiscountStatus). The
// backend validates every value and works out every price; these only drive the controls.
export const DISCOUNT_KINDS = [
  { value: "percentage", label: "Percentage" },
  { value: "fixed", label: "Fixed amount" },
];
export const DISCOUNT_KIND_LABEL = Object.fromEntries(DISCOUNT_KINDS.map((k) => [k.value, k.label]));

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
