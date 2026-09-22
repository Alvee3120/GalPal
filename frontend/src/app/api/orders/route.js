import { cookies } from "next/headers";
import { backendFetch } from "@/lib/backendAuth";

// Thin proxy to the EXISTING orders API — the backend URL stays server-side, and a session (if any) always comes
// from the token, never from anything the browser claims. Two real backend endpoints live under this one path:
//   POST /api/v1/checkout/   place an order from the cart (guest cart token, or the logged-in customer)
//   GET  /api/v1/orders/     the logged-in customer's own orders (MyOrderViewSet; 401 for a guest — real backend rule)
// The browser never sends a delivery charge, a total, or who's ordering — only the address for THIS order; the
// server prices it and identifies the customer itself.
const ALLOWED_LIST_PARAMS = ["page", "page_size", "status", "ordering"];

export async function GET(request) {
  const incoming = new URL(request.url).searchParams;
  const params = new URLSearchParams();
  for (const key of ALLOWED_LIST_PARAMS) {
    if (incoming.has(key)) params.set(key, incoming.get(key));
  }
  let res;
  try {
    res = await backendFetch(`/orders/?${params}`);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export async function POST(request) {
  const body = await request.text();
  const store = await cookies();
  const cartToken = store.get("cart_token")?.value;

  let res;
  try {
    res = await backendFetch("/checkout/", { method: "POST", body, headers: cartToken ? { "X-Cart-Token": cartToken } : {} });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
