import { backendFetch } from "@/lib/backendAuth";

// Proxy to User Management (apps.accounts.views.UserViewSet at /admin/users/ — IsAdmin backend-side, the real
// authorization). Forwards list/search/filter, create, retrieve, edit and delete only. Passwords travel in the request
// body (never the URL) and the backend never returns them.
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
    let body;
    if (method === "POST" || method === "PATCH") {
      // An avatar goes up as multipart: re-send the parsed FormData so fetch writes its own boundary (see backendFetch).
      const isForm = (request.headers.get("content-type") ?? "").startsWith("multipart/form-data");
      body = isForm ? await request.formData() : await request.text();
    }
    res = await backendFetch(`/admin/users/${path.length ? `${path[0]}/` : ""}${qs}`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.status === 204) return new Response(null, { status: 204 });
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
