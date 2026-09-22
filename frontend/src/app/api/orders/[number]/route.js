import { backendFetch } from "@/lib/backendAuth";

// Proxy to the EXISTING GET /orders/<number>/ (MyOrderViewSet.retrieve) — the logged-in customer's own order,
// full detail (items, address, status history, totals). The backend scopes this to `request.user` and 404s for
// anyone else's order number (see apps.accounts.permissions.IsOwner) — this route trusts that entirely; it never
// filters or checks ownership itself.
export async function GET(request, { params }) {
  const { number } = await params;
  let res;
  try {
    res = await backendFetch(`/orders/${encodeURIComponent(number)}/`);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
