import { backendFetch } from "@/lib/backendAuth";

// Proxy to the Notifications admin API (apps.notifications.views_admin — IsAdmin: CCE and customers get 403 there),
// narrowed to the routes the dashboard uses.
const ID = /^\d+$/;
const SLUG = /^[a-z_]+$/;
const isPath = (p, method) => {
  const [area, a, b] = p;
  if (area === "logs") {
    if (p.length === 1) return method === "GET";
    if (p.length === 2 && ID.test(a)) return method === "GET";
    return p.length === 3 && ID.test(a) && b === "retry" && method === "POST";
  }
  if (area === "templates") {
    if (p.length === 1) return method === "GET";
    return p.length === 3 && SLUG.test(a) && SLUG.test(b) && (method === "PUT" || method === "DELETE");
  }
  return false;
};

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });
  const qs = new URL(request.url).search;
  const body = method === "PUT" ? (await request.text()) || undefined : undefined;
  let res;
  try {
    res = await backendFetch(`/admin/notifications/${path.join("/")}/${qs}`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PUT, handler as DELETE };
