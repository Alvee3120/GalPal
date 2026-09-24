// Shared bits for the CCE Product Management pages (component/dashboard/products/*).
//
// The option lists mirror the backend's TextChoices in apps/catalog/models.py exactly (value -> label); the backend
// validates every value, so these only drive the form controls. Keep them in sync with that file.
export const PRODUCT_STATUS = [
  { value: "draft", label: "Draft" },
  { value: "published", label: "Published" },
  { value: "archived", label: "Archived" },
];
export const PRODUCT_STATUS_LABEL = Object.fromEntries(PRODUCT_STATUS.map((o) => [o.value, o.label]));

export const STOCK_STATUS = [
  { value: "in_stock", label: "In stock" },
  { value: "out_of_stock", label: "Out of stock" },
  { value: "backorder", label: "Backorder" },
];
export const STOCK_STATUS_LABEL = Object.fromEntries(STOCK_STATUS.map((o) => [o.value, o.label]));

export const SKIN_TYPES = [
  { value: "oily", label: "Oily" },
  { value: "dry", label: "Dry" },
  { value: "combination", label: "Combination" },
  { value: "normal", label: "Normal" },
  { value: "sensitive", label: "Sensitive" },
  { value: "all", label: "All skin types" },
];

export const SIZE_UNITS = ["ml", "l", "g", "kg", "pcs", "oz"].map((value) => ({ value, label: value === "l" ? "L" : value }));

export const GENDERS = [
  { value: "unisex", label: "Unisex" },
  { value: "women", label: "Women" },
  { value: "men", label: "Men" },
  { value: "kids", label: "Kids" },
];

// Every call goes through the /api/admin/catalog proxy (app/api/admin/catalog/[[...path]]/route.js). Resolves to
// { ok, status, data } and never throws, so callers only branch on `ok`.
export async function catalogFetch(path, { method = "GET", body } = {}) {
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  try {
    const res = await fetch(`/api/admin/catalog/${path}`, {
      method,
      cache: "no-store",
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      headers: body === undefined || isForm ? undefined : { "Content-Type": "application/json" },
    });
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, data };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

// Every page of a paginated list endpoint (brands, tags, attributes: small admin-managed lists).
export async function catalogFetchAll(path) {
  const items = [];
  for (let page = 1; page <= 20; page += 1) {
    const sep = path.includes("?") ? "&" : "?";
    const res = await catalogFetch(`${path}${sep}page_size=100&page=${page}`);
    if (!res.ok) return null;
    items.push(...(res.data?.results ?? []));
    if (!res.data?.next) break;
  }
  return items;
}

const FIELD_LABEL = {
  non_field_errors: "",
  detail: "",
  feature_image: "Feature image",
  og_image: "OG image",
  regular_price: "Regular price",
  discount_price: "Discount price",
  sale_start_at: "Sale start",
  sale_end_at: "Sale end",
  sku: "SKU",
  slug: "Slug",
  attribute_value_ids: "Variant options",
  attribute_values: "Variant options",
  quantity_change: "Stock",
  primary_category: "Primary category",
  categories: "Categories",
};

// The backend's error envelope ({ error: { message, details: { field: [msg] } } }) as one readable line, naming
// the field so a message like "Must be less than the regular price." still makes sense in a toast.
export function errorText(res, fallback) {
  if (!res || res.status === 0) return "We couldn't reach the server. Please try again.";
  if (res.status === 403) return "You don't have permission to do that.";
  const error = res.data?.error;
  const details = error?.details;
  if (details && typeof details === "object") {
    for (const [field, value] of Object.entries(details)) {
      const message = [value].flat(Infinity).find((m) => typeof m === "string");
      if (!message) continue;
      const label = FIELD_LABEL[field] ?? field.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
      return label ? `${label}: ${message}` : message;
    }
  }
  return error?.message && res.status < 500 ? error.message : fallback;
}

// Sale dates: the backend stores aware datetimes and reads a naive "YYYY-MM-DDTHH:MM" in its own TIME_ZONE
// (config/settings/base.py: Asia/Dhaka), so the form shows and sends wall-clock time in that zone, whatever the
// browser's own zone is.
export const STORE_TIME_ZONE = "Asia/Dhaka";

export function splitStoreDateTime(iso) {
  if (!iso) return { date: "", time: "" };
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { date: "", time: "" };
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: STORE_TIME_ZONE, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    })
      .formatToParts(d)
      .map((p) => [p.type, p.value]),
  );
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}

export function joinStoreDateTime(date, time) {
  if (!date) return null;
  return `${date}T${time || "00:00"}`;
}
