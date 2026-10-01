import { backendFetch } from "@/lib/backendAuth";

// Proxy to the wishlist API (apps.cart.views_wishlist, logged-in users only — a guest gets the backend's 401).
//   GET  -> GET  /wishlist/   the customer's saved products
//   POST -> POST /wishlist/   { product_id } save one (idempotent)
async function relay(path, init) {
  let res;
  try {
    res = await backendFetch(path, init);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export async function GET() {
  return relay("/wishlist/");
}

export async function POST(request) {
  const { product_id } = (await request.json().catch(() => null)) ?? {};
  return relay("/wishlist/", { method: "POST", body: JSON.stringify({ product_id }) });
}
