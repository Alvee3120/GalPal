import { cookies } from "next/headers";

// Thin proxy for placing an order (POST /orders/checkout/), same shape as the /api/cart proxy: the backend URL stays
// server-side, the guest cart token cookie identifies the cart being ordered, and a logged-in customer's JWT is
// attached when present. The browser never sends a delivery charge or a total — only the address (city + zone)
// and contact details; the server must price the order from its own cart and shipping rules.
//
// NOTE: the backend has no orders endpoint yet (orders are a later backend module). Until one exists this call
// gets a 404 and the customer sees a real, non-faked error toast; nothing here pretends an order was saved.
const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";

export async function POST(request) {
  const body = await request.text();
  const store = await cookies();

  const headers = { Accept: "application/json", "Content-Type": "application/json" };
  const cartToken = store.get("cart_token")?.value;
  if (cartToken) headers["X-Cart-Token"] = cartToken;
  const access = store.get("access_token")?.value;
  if (access) headers.Authorization = `Bearer ${access}`;

  let res;
  try {
    res = await fetch(`${API_BASE_URL}/orders/checkout/`, { method: "POST", headers, body, cache: "no-store" });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
