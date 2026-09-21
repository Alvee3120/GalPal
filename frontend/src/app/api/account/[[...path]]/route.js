import { backendFetch } from "@/lib/backendAuth";

// Thin proxy to the EXISTING account endpoints the checkout needs — GET|PATCH /account/profile/ and
// GET|POST|PATCH /account/addresses/[id/[set-default/]] — acting as the logged-in customer (the identity always comes
// from the session token, never from anything the browser sends). Nothing else under /account is reachable here.
const isAccountPath = (path) =>
  (path.length === 1 && path[0] === "profile") ||
  (path[0] === "addresses" &&
    (path.length === 1 ||
      (/^\d+$/.test(path[1]) && (path.length === 2 || (path.length === 3 && path[2] === "set-default")))));

async function handler(request, { params }) {
  const { path = [] } = await params;
  if (!isAccountPath(path)) return Response.json({ error: { message: "Not found." } }, { status: 404 });

  const method = request.method;
  const body = method === "GET" ? undefined : await request.text();

  let res;
  try {
    res = await backendFetch(`/account/${path.join("/")}/`, { method, body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH };
