// Client helper for the Notifications admin API (Module 16) via the /api/admin/notifications proxy. Resolves to
// { ok, status, data } and never throws, like the other dashboard fetch helpers.
export async function notificationsFetch(path, { method = "GET", body } = {}) {
  try {
    const res = await fetch(`/api/admin/notifications/${path}`, {
      method,
      cache: "no-store",
      body: body === undefined ? undefined : JSON.stringify(body),
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    });
    return { ok: res.ok, status: res.status, data: await res.json().catch(() => null) };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

// Mirrors apps.notifications.models.Event / LogStatus.
export const EVENT_LABEL = {
  order_placed: "Order placed",
  order_status_changed: "Order status changed",
  password_reset_otp: "Password reset code",
  new_account: "New account details",
  low_stock: "Low stock alert (to admins)",
  review_reply: "Reply to a review",
  back_in_stock: "Back in stock (Notify Me)",
};
export const CHANNEL_LABEL = { email: "Email", sms: "SMS" };
export const LOG_STATUS_LABEL = { queued: "Queued", retrying: "Retrying", sent: "Sent", failed: "Failed" };
export const LOG_STATUS_TONE = { queued: "draft", retrying: "draft", sent: "active", failed: "archived" };
