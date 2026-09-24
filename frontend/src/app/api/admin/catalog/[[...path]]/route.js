import { backendFetch } from "@/lib/backendAuth";

// Thin proxy to the EXISTING catalog admin API (apps.catalog.views_product_admin / views_admin) for the CCE Product,
// Category and Brand Management pages. /api/admin/catalog/<rest> forwards to /admin/<rest>/. The backend's IsCatalogStaff (per-action
// `cce_actions`) is the real authorization boundary; this list only mirrors the endpoints those pages use
// (apps.accounts.tests.route_sweep.CCE_CATALOG_ENDPOINTS), so nothing else is reachable through here either.
const ID = /^\d+$/;
const isPath = (p, method) => {
  const [resource, id, sub, subId] = p;
  if (resource === "products") {
    if (p.length === 1) return method === "GET" || method === "POST"; // list+search / create
    if (!ID.test(id ?? "")) return false;
    if (p.length === 2) return ["GET", "PATCH", "DELETE"].includes(method);
    if (sub !== "images" && sub !== "variants") return false;
    if (p.length === 3) return method === "GET" || method === "POST";
    if (p.length === 4 && sub === "images" && subId === "reorder") return method === "POST";
    if (p.length === 4 && ID.test(subId)) return method === "PATCH" || method === "DELETE";
    return false;
  }
  if (resource === "stock") return p.length === 2 && id === "adjust" && method === "POST";
  if (resource === "stock-notifications") {
    if (p.length === 1) return method === "GET"; // Notify Me requests
    return p.length === 2 && ID.test(id) && method === "PATCH"; // mark waiting / notified
  }
  if (resource === "categories") {
    if (p.length === 1) return method === "GET" || method === "POST"; // list+search / create
    if (p.length === 2 && id === "tree") return method === "GET";
    return p.length === 2 && ID.test(id) && ["GET", "PATCH", "DELETE"].includes(method); // retrieve / edit / delete
  }
  if (resource === "brands") {
    if (p.length === 1) return method === "GET" || method === "POST"; // list+search / create
    return p.length === 2 && ID.test(id) && ["GET", "PATCH", "DELETE"].includes(method); // retrieve / edit / delete
  }
  if (resource === "product-attributes") return method === "GET" && p.length === 1;
  if (resource === "tags" || resource === "attribute-values") return p.length === 1 && (method === "GET" || method === "POST");
  return false;
};

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });

  const qs = new URL(request.url).search;
  let body;
  if (method !== "GET" && method !== "DELETE") {
    // Images go up as multipart: re-send the parsed FormData so fetch writes its own boundary (see backendFetch).
    const isForm = (request.headers.get("content-type") ?? "").startsWith("multipart/form-data");
    body = isForm ? await request.formData() : await request.text();
  }

  let res;
  try {
    res = await backendFetch(`/admin/${path.join("/")}/${qs}`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.status === 204) return new Response(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
