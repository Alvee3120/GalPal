import { backendFetch } from "@/lib/backendAuth";

// Proxy to the EXISTING POST /orders/<number>/cancel/ (MyOrderViewSet.cancel) — only the logged-in owner of that
// order can cancel it, and only while it's still pending/confirmed; the backend enforces both, this just forwards.
export async function POST(request, { params }) {
  const { number } = await params;
  const body = await request.text();
  let res;
  try {
    res = await backendFetch(`/orders/${encodeURIComponent(number)}/cancel/`, { method: "POST", body: body || "{}" });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
