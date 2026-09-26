import { backendFetch } from "@/lib/backendAuth";

// Proxy for Delivery Charges (apps.shipping.views_admin.AdminZoneViewSet — IsAdmin backend-side): list the zones, and
// change one zone's charge (PATCH zones/<id>/charge/, which validates it and logs who changed it from what to what),
// and edit a zone's areas (PATCH zones/<id>/ with `coverage`, checked so no two zones claim the same area).
const ID = /^\d+$/;
const isPath = (p, method) =>
  (p.length === 1 && p[0] === "zones" && method === "GET") ||
  (p.length === 2 && p[0] === "zones" && ID.test(p[1]) && method === "PATCH") || // edit a zone (its coverage/areas)
  (p.length === 3 && p[0] === "zones" && ID.test(p[1]) && p[2] === "charge" && method === "PATCH");

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });
  const qs = new URL(request.url).search;
  let res;
  try {
    res = await backendFetch(`/admin/shipping/${path.join("/")}/${qs}`, { method, body: method === "PATCH" ? await request.text() : undefined });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as PATCH };
