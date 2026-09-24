import { backendFetch } from "@/lib/backendAuth";

// Thin proxy to the backend's "Notify Me" endpoint (POST /stock-notifications/,
// apps.catalog.views_stock_notification.StockNotificationView). backendFetch attaches the logged-in customer's
// token — renewing it when the 15-minute access token has lapsed — so the backend texts the account's own phone;
// a guest has no session and sends their phone number in the body instead.
export async function POST(request) {
  const body = await request.text();
  let res;
  try {
    res = await backendFetch("/stock-notifications/", { method: "POST", body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
