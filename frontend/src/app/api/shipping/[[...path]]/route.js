import { cookies } from "next/headers";
import { backendFetch } from "@/lib/backendAuth";

// Storefront delivery charges, from the backend's shipping zones (apps.shipping — the ONE place charges live; the
// Admin edits them on Dashboard -> Delivery Charges):
//   GET  /api/shipping/zones  -> GET /shipping/zones/       active zones with their charge (cart summary rates)
//   POST /api/shipping/quote  -> POST /shipping/calculate/  the charge for {district, area} against the current cart
// The quote carries the cart token / login, so the backend applies the cart's subtotal and coupon (free-delivery rules)
// exactly as checkout will. It's a preview: checkout recomputes the charge on the server and never accepts one from here.
async function handler(request, { params }) {
  const { path = [] } = await params;
  const method = request.method;
  const route = path.join("/");
  if (!((route === "zones" && method === "GET") || (route === "quote" && method === "POST"))) {
    return Response.json({ error: { message: "Not found." } }, { status: 404 });
  }

  let body;
  if (route === "quote") {
    const incoming = await request.json().catch(() => ({}));
    body = JSON.stringify({ district: String(incoming.district ?? ""), area: String(incoming.area ?? "") });
  }
  const cartToken = (await cookies()).get("cart_token")?.value;

  let res;
  try {
    res = await backendFetch(route === "zones" ? "/shipping/zones/" : "/shipping/calculate/", {
      method,
      body,
      headers: cartToken ? { "X-Cart-Token": cartToken } : {},
    });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST };
