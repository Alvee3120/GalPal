import { backendFetch } from "@/lib/backendAuth";

// Proxy to DELETE /wishlist/<product_id>/ — remove one saved product (logged-in users only).
export async function DELETE(request, { params }) {
  const { productId } = await params;
  if (!/^\d+$/.test(productId)) return Response.json({ error: { message: "Not found." } }, { status: 404 });
  let res;
  try {
    res = await backendFetch(`/wishlist/${productId}/`, { method: "DELETE" });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
