import { backendFetch } from "@/lib/backendAuth";

// Thin proxy to the EXISTING /admin/orders/* API (apps.orders.views_admin.AdminOrderViewSet + its 3 read-only
// helper views) — the ONLY admin-prefixed area a CCE account may reach (apps.accounts.permissions.IsAdminOrCCE
// enforces this backend-side; nothing here decides who may act, it only forwards whatever the backend answers,
// including a 401/403). Deliberately narrow to the actions this dashboard actually uses: list/search, create a
// manual order, retrieve, edit a pending order's items/contact, and change status. Delete and shipping-override
// are Admin-only backend-side and aren't needed by the CCE UI, so they're left unreachable here too.
const isPath = (path, method) => {
  if (path.length === 0) return method === "GET" || method === "POST"; // list+filter / create manual order
  if (path.length === 1 && path[0] === "dashboard") return method === "GET"; // dashboard overview numbers
  if (path.length === 2 && path[0] === "helpers") return method === "GET" && ["products", "shipping", "customers"].includes(path[1]);
  if (path.length === 1 && /^\d+$/.test(path[0])) return method === "GET" || method === "PATCH"; // retrieve / edit pending order
  if (path.length === 2 && /^\d+$/.test(path[0]) && path[1] === "status") return method === "POST"; // change status
  return false;
};

async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  if (!isPath(path, method)) return Response.json({ error: { message: "Not found." } }, { status: 404 });

  const qs = new URL(request.url).search;
  const body = method === "GET" ? undefined : await request.text();

  let res;
  try {
    res = await backendFetch(`/admin/orders/${path.join("/")}${path.length ? "/" : ""}${qs}`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH };
