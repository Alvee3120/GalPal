import { messageFor } from "./apiError";

const ALREADY_SUBSCRIBED = "You're already on the notification list for this product.";
const UNABLE = "Unable to request a stock notification. Please try again.";

// Shared by the logged-in (no modal) and guest (modal) Notify Me flows: same endpoint, same
// response handling, so the two paths can't drift into different error/duplicate behavior.
// `phone` is omitted for a logged-in request — the backend identifies the subscriber from the
// Authorization header the /api/stock-notifications proxy attaches, not from anything re-typed here.
export async function requestStockNotification({ productId, variantId, phone }) {
  try {
    const res = await fetch("/api/stock-notifications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: productId, variant_id: variantId ?? undefined, phone: phone ?? undefined }),
      cache: "no-store",
    });
    const data = await res.json().catch(() => null);
    if (res.ok) return { ok: true };
    if (res.status === 409) return { ok: false, message: data?.error?.message || ALREADY_SUBSCRIBED };
    return { ok: false, message: messageFor({ status: res.status, details: data?.error?.details }, UNABLE) };
  } catch {
    return { ok: false, message: "Something went wrong. Please try again." };
  }
}
