import { backendFetch } from "@/lib/backendAuth";

// Proxy to POST /newsletter/subscribe/ (apps.content — throttled per IP backend-side). Only the form's fields.
export async function POST(request) {
  const { email, phone, source } = (await request.json().catch(() => null)) ?? {};
  let res;
  try {
    res = await backendFetch("/newsletter/subscribe/", { method: "POST", body: JSON.stringify({ email, phone, source }) });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
