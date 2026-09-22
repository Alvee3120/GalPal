import { cookies } from "next/headers";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";

// Mirrors the backend's JWT lifetimes and the cookie settings used by the login actions (app/actions/auth.js).
const ACCESS_MAX_AGE = 60 * 15;
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7;
const COOKIE_BASE = { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/" };

// The backend burns a refresh token the moment it is used, so two requests arriving together with the same expired
// session (say the cart and the account, on page load) must share ONE renewal — otherwise the second one is refused
// and that request wrongly acts as a guest. The result is kept briefly for requests that were already in flight
// carrying the old cookie.
const renewals = new Map();
const RENEWAL_SHARE_MS = 15000;

function renewOnce(refresh, renew) {
  if (!renewals.has(refresh)) {
    renewals.set(refresh, renew());
    setTimeout(() => renewals.delete(refresh), RENEWAL_SHARE_MS);
  }
  return renewals.get(refresh);
}

// Route handlers only: calls the backend as the logged-in customer. The access token lives 15 minutes (its cookie
// disappears with it) while the refresh token lasts 7 days, so a still-logged-in customer often has no usable
// access token — this trades the refresh token for a new one (and stores it) instead of silently acting as a guest.
// Nothing is sent as a guest if there is no session at all.
export async function backendFetch(path, { method = "GET", body, headers = {} } = {}) {
  const store = await cookies();
  // A FormData body (e.g. a review's optional images) must NOT get a JSON content-type: fetch sets its own
  // multipart boundary from the FormData object, which a hardcoded "application/json" would stomp.
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  const call = (access) =>
    fetch(`${API_BASE_URL}${path}`, {
      method,
      body,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(isForm ? {} : { "Content-Type": "application/json" }),
        ...headers,
        ...(access ? { Authorization: `Bearer ${access}` } : {}),
      },
    });

  async function refreshAccess() {
    const refresh = store.get("refresh_token")?.value;
    if (!refresh) return null;
    try {
      const data = await renewOnce(refresh, async () => {
        const res = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ refresh }),
          cache: "no-store",
        });
        return res.ok ? res.json() : null;
      });
      if (!data) return null;
      store.set("access_token", data.access, { ...COOKIE_BASE, maxAge: ACCESS_MAX_AGE });
      if (data.refresh) store.set("refresh_token", data.refresh, { ...COOKIE_BASE, maxAge: REFRESH_MAX_AGE });
      return data.access;
    } catch {
      return null;
    }
  }

  let access = store.get("access_token")?.value ?? (await refreshAccess());
  let res = await call(access);
  if (res.status === 401 && access && store.get("refresh_token")?.value) {
    const renewed = await refreshAccess();
    if (renewed) res = await call(renewed);
  }
  return res;
}
