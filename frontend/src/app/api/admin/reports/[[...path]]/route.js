import { backendFetch } from "@/lib/backendAuth";

// Proxy to the CSV exports (apps.reports — IsAdmin: CCE and customers get 403 there), passed through as file downloads.
// The report figures themselves come with the Admin dashboard (GET /admin/dashboard/ → `reports`).
const EXPORTS = new Set(["orders", "products", "customers"]);

export async function GET(request, { params }) {
  const { path = [] } = await params;
  const isExport = path.length === 2 && path[0] === "export" && EXPORTS.has(path[1]);
  if (!isExport) return Response.json({ error: { message: "Not found." } }, { status: 404 });
  const qs = new URL(request.url).search;
  let res;
  try {
    res = await backendFetch(`/admin/reports/${path.join("/")}/${qs}`);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  if (res.ok) {
    return new Response(res.body, {
      status: 200,
      headers: {
        "Content-Type": res.headers.get("Content-Type") ?? "text/csv; charset=utf-8",
        "Content-Disposition": res.headers.get("Content-Disposition") ?? `attachment; filename=${path[1]}.csv`,
        "Cache-Control": "no-store",
      },
    });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
