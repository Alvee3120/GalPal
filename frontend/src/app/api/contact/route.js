import { backendFetch } from "@/lib/backendAuth";

// Proxy to POST /contact/ (apps.care — the public contact form; throttled per IP backend-side). Only the form's own
// fields are forwarded.
export async function POST(request) {
  const { name, phone, email, subject, message } = (await request.json().catch(() => null)) ?? {};
  let res;
  try {
    res = await backendFetch("/contact/", { method: "POST", body: JSON.stringify({ name, phone, email, subject, message }) });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
