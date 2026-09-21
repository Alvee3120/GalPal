import { cookies } from "next/headers";
import { backendFetch } from "@/lib/backendAuth";

// Thin proxy for placing an order (POST /orders/checkout/), same shape as the /api/cart proxy: the backend URL stays
// server-side, the guest cart token cookie identifies the cart being ordered, and a logged-in customer is identified by
// their session token (renewed from the refresh token when the short-lived access token has lapsed — see backendAuth).
// The browser never sends a delivery charge, a total, or who the customer is — only the address (city + zone) and contact
// details for THIS order; the server must price the order and identify the customer itself.
//
// NOTE: the backend has no orders endpoint yet (orders are a later backend module). Until one exists this call
// gets a 404 and the customer sees a real, non-faked error toast; nothing here pretends an order was saved.
export async function POST(request) {
  const body = await request.text();
  const store = await cookies();
  const cartToken = store.get("cart_token")?.value;

  let res;
  try {
    res = await backendFetch("/orders/checkout/", { method: "POST", body, headers: cartToken ? { "X-Cart-Token": cartToken } : {} });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
