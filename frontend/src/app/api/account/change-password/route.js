import { cookies } from "next/headers";
import { backendFetch } from "@/lib/backendAuth";

// Mirrors the cookie settings the login/refresh flows already use (lib/backendAuth.js, app/actions/auth.js).
const ACCESS_MAX_AGE = 60 * 15;
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7;
const COOKIE_BASE = { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/" };

// Proxy to the EXISTING POST /auth/password/change/ (accounts.views.ChangePasswordView) — the only password-change
// endpoint in the backend, already requiring the current password and validating the new one with Django's own
// validators. It blacklists every other session's refresh token and returns a fresh access/refresh pair for THIS
// session, so on success those replace the existing httpOnly cookies here (same mechanism the login action uses)
// instead of leaving the browser holding tokens the backend just invalidated. The raw tokens never reach the
// client's JS — only a plain success/error body does.
export async function POST(request) {
  const body = await request.text();
  let res;
  try {
    res = await backendFetch("/auth/password/change/", { method: "POST", body });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });

  if (data?.access && data?.refresh) {
    const store = await cookies();
    store.set("access_token", data.access, { ...COOKIE_BASE, maxAge: ACCESS_MAX_AGE });
    store.set("refresh_token", data.refresh, { ...COOKIE_BASE, maxAge: REFRESH_MAX_AGE });
  }
  return Response.json({ detail: data?.detail ?? "Password changed." }, { status: 200, headers: { "Cache-Control": "no-store" } });
}
