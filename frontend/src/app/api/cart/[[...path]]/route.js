import { cookies } from "next/headers";

// Thin proxy to the backend cart API (GET /cart/, POST /cart/items/, PATCH|DELETE /cart/items/{id}/).
// The backend URL stays server-side; the guest cart token lives in an httpOnly cookie (so the cart survives
// refreshes), and the logged-in user's JWT (from the auth cookie) is attached when present.
const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const BACKEND_ORIGIN = new URL(API_BASE_URL).origin;
const CART_TOKEN_MAX_AGE = 60 * 60 * 24 * 30;

const isCartPath = (path) =>
  path.length === 0 || (path[0] === "items" && path.length <= 2 && (path[1] === undefined || /^\d+$/.test(path[1])));

async function callBackend(url, method, body, headers) {
  return fetch(url, { method, headers, body, cache: "no-store" });
}

async function handler(request, { params }) {
  const { path = [] } = await params;
  if (!isCartPath(path)) return Response.json({ error: { message: "Not found." } }, { status: 404 });

  const store = await cookies();
  const url = `${API_BASE_URL}/cart/${path.length ? `${path.join("/")}/` : ""}`;
  const method = request.method;
  const body = method === "GET" || method === "DELETE" ? undefined : await request.text();

  const headers = { Accept: "application/json", "Content-Type": "application/json" };
  const cartToken = store.get("cart_token")?.value;
  if (cartToken) headers["X-Cart-Token"] = cartToken;
  const access = store.get("access_token")?.value;

  let res;
  try {
    res = await callBackend(url, method, body, access ? { ...headers, Authorization: `Bearer ${access}` } : headers);
    // An expired access token must not break the cart: retry as a guest.
    if (res.status === 401 && access) res = await callBackend(url, method, body, headers);
  } catch {
    return Response.json({ error: { message: "We couldn't reach the cart service." } }, { status: 502 });
  }

  const data = await res.json().catch(() => null);

  if (data?.cart_token) {
    store.set("cart_token", data.cart_token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: CART_TOKEN_MAX_AGE,
    });
  }

  // Cart item images come back as relative /media paths; make them absolute for the browser.
  for (const item of data?.items ?? []) {
    const img = item.product?.feature_image;
    if (typeof img === "string" && img.startsWith("/")) item.product.feature_image = BACKEND_ORIGIN + img;
  }

  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
