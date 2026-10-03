import { backendFetch } from "@/lib/backendAuth";

// Proxy to GET /admin/audit-logs/ (apps.audit — IsAdmin: CCE and customers get 403 there). Read-only.
export async function GET(request) {
  const qs = new URL(request.url).search;
  let res;
  try {
    res = await backendFetch(`/admin/audit-logs/${qs}`);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
