const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;
// Cache tag for everything the storefront shows about Admin discounts; the admin Discounts proxy revalidates it after
// every change, so a new / renamed / switched-off discount shows on the homepage right away.
export const DISCOUNTS_TAG = "discounts";

// The Admin discounts live right now that are pricing at least one published product (GET /discounts/active/ —
// apps.discounts.views). [] if the backend can't be reached, so the homepage simply shows no discount sections.
export async function getActiveDiscounts() {
  try {
    const res = await fetch(`${API_BASE_URL}/discounts/active/`, { next: { revalidate: REVALIDATE_SECONDS, tags: [DISCOUNTS_TAG] } });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}
