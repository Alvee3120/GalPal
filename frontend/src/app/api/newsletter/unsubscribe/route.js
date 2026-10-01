import { backendFetch } from "@/lib/backendAuth";

// Proxy to POST /newsletter/unsubscribe/ with the token from the unsubscribe link.
export async function POST(request) {
  const { token } = (await request.json().catch(() => null)) ?? {};
  let res;
  try {
    res = await backendFetch("/newsletter/unsubscribe/", { method: "POST", body: JSON.stringify({ token }) });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
