import { backendFetch } from "@/lib/backendAuth";

// Proxy to /orders/<number>/return-request/ (apps.care): the logged-in customer's return requests for their OWN order
// (the backend scopes it and 404s for anyone else's). GET lists them, POST {reason, details} creates one.
async function relay(number, init) {
  let res;
  try {
    res = await backendFetch(`/orders/${encodeURIComponent(number)}/return-request/`, init);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export async function GET(request, { params }) {
  return relay((await params).number);
}

export async function POST(request, { params }) {
  const { reason, details } = (await request.json().catch(() => null)) ?? {};
  return relay((await params).number, { method: "POST", body: JSON.stringify({ reason, details }) });
}
