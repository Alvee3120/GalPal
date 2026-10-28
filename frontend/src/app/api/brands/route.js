const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const ALLOWED_PARAMS = ["category", "page_size"];

// Thin proxy to the EXISTING public GET /brands/ (apps.catalog.views.PublicBrandViewSet, AllowAny). The Shop mega
// menu is a CLIENT component and needs the brands inside the hovered category (`?category=<slug>`) from the browser;
// narrowed to just the params it sends, the same allow-list style as the other proxies in this app.
export async function GET(request) {
  const incoming = new URL(request.url).searchParams;
  const params = new URLSearchParams();
  for (const key of ALLOWED_PARAMS) {
    if (incoming.has(key)) params.set(key, incoming.get(key));
  }
  let res;
  try {
    res = await fetch(`${API_BASE_URL}/brands/?${params}`, { cache: "no-store" });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
