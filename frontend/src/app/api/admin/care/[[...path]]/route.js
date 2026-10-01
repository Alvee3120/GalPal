import { backendFetch } from "@/lib/backendAuth";

// Proxy to the Customer Care admin API (apps.care.views_admin — IsAdmin: CCE and customers get 403 there).
// Narrowed to the routes the dashboard uses.
const ID = /^\d+$/;
const isPath = (p, method) => {
  const [area, id, sub] = p;
  if (area === "customers" && ID.test(id ?? "")) {
    if (p.length === 2) return method === "GET";
    if (p.length === 3 && sub === "notes") return method === "POST";
    if (p.length === 3 && sub === "tags") return method === "PUT";
  }
  if (area === "notes" && p.length === 2 && ID.test(id)) return method === "DELETE";
  if (area === "tags" && p.length === 1) return method === "GET";
  if (area === "messages") {
    if (p.length === 1) return method === "GET";
    if (p.length === 2 && ID.test(id)) return method === "GET" || method === "PATCH";
    if (p.length === 3 && ID.test(id) && sub === "notes") return method === "POST";
  }
  if (area === "abandoned-checkouts") return p.length === 1 ? method === "GET" : p.length === 2 && ID.test(id) && method === "PATCH";
  return false;
};

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });
  const qs = new URL(request.url).search;
  const body = method === "GET" || method === "DELETE" ? undefined : (await request.text()) || undefined;
  let res;
  try {
    res = await backendFetch(`/admin/care/${path.join("/")}/${qs}`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.status === 204) return new Response(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH, handler as PUT, handler as DELETE };
