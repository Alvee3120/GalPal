import { backendFetch } from "@/lib/backendAuth";

// Proxy to Coupon Management (apps.coupons.views_admin.AdminCouponViewSet — IsAdmin backend-side, the real
// authorization): list/search/filter, create, retrieve, edit, delete.
const ID = /^\d+$/;
const isPath = (p, method) => {
  if (p.length === 0) return method === "GET" || method === "POST";
  return p.length === 1 && ID.test(p[0]) && ["GET", "PATCH", "DELETE"].includes(method);
};

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });
  const qs = new URL(request.url).search;
  let res;
  try {
    res = await backendFetch(`/admin/coupons/${path.length ? `${path[0]}/` : ""}${qs}`, {
      method,
      body: method === "POST" || method === "PATCH" ? await request.text() : undefined,
    });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.status === 204) return new Response(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
