import { backendFetch } from "@/lib/backendAuth";

// Proxy to the Admin dashboard numbers (GET /admin/dashboard/, apps.orders.views_admin.AdminDashboardView — IsAdmin
// backend-side). Only the date range is forwarded.
export async function GET(request) {
  const incoming = new URL(request.url).searchParams;
  const params = new URLSearchParams();
  for (const key of ["date_from", "date_to"]) if (incoming.get(key)) params.set(key, incoming.get(key));
  let res;
  try {
    res = await backendFetch(`/admin/dashboard/?${params}`);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
