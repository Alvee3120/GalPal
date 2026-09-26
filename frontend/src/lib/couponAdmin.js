// Coupon Management constants, mirroring apps.coupons.models.CouponType and services.status_of exactly (the backend
// validates every value; these only drive the controls).
export const COUPON_TYPES = [
  { value: "percentage", label: "Percentage" },
  { value: "flat", label: "Fixed amount" },
];
export const COUPON_TYPE_LABEL = Object.fromEntries(COUPON_TYPES.map((t) => [t.value, t.label]));

export const COUPON_STATUSES = [
  { value: "active", label: "Active" },
  { value: "scheduled", label: "Scheduled" },
  { value: "expired", label: "Expired" },
  { value: "used_up", label: "Used up" },
  { value: "inactive", label: "Inactive" },
];
export const COUPON_STATUS_LABEL = Object.fromEntries(COUPON_STATUSES.map((s) => [s.value, s.label]));

export async function couponFetch(path = "", { method = "GET", body } = {}) {
  try {
    const res = await fetch(`/api/admin/coupons${path}`, {
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
