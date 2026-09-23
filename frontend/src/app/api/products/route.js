const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const ALLOWED_PARAMS = ["search", "page_size"];

// Thin proxy to the EXISTING public GET /products/ (apps.catalog.views_product.PublicProductViewSet, AllowAny —
// the same list endpoint the Shop page already reads server-side via lib/shopData.js). This exists only because
// the storefront's live search dropdown (component/shared/Navbar.jsx) is a CLIENT component and needs to call it
// from the browser; narrowed to just the params that dropdown actually sends, same allowlist style as the other
// proxies in this app.
export async function GET(request) {
  const incoming = new URL(request.url).searchParams;
  const params = new URLSearchParams();
  for (const key of ALLOWED_PARAMS) {
    if (incoming.has(key)) params.set(key, incoming.get(key));
  }
  let res;
  try {
    res = await fetch(`${API_BASE_URL}/products/?${params}`, { cache: "no-store" });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
