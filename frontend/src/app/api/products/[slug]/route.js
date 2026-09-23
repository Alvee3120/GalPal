const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";

// Thin proxy to the EXISTING public GET /products/<slug>/ (apps.catalog.views_product.PublicProductViewSet,
// AllowAny — the same endpoint the storefront's product detail page already reads server-side). No auth needed;
// this exists only because that endpoint previously had no CLIENT-side caller — the CCE order product picker
// (ProductSearchPicker) needs it to fetch a variable product's real variants/attributes (the same shape
// component/product/ProductDetailContent.jsx already renders) once a CCE selects a product that has variants.
export async function GET(request, { params }) {
  const { slug } = await params;
  let res;
  try {
    res = await fetch(`${API_BASE_URL}/products/${encodeURIComponent(slug)}/`, { cache: "no-store" });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
