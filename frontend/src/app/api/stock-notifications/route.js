import { cookies } from "next/headers";

// Thin proxy to the backend's back-in-stock notification endpoint (POST /stock-notifications/) —
// same shape as the /api/cart proxy: the backend URL stays server-side, and the logged-in user's
// JWT (from the auth cookie) is attached when present, so a future backend endpoint can identify
// the subscriber from the token instead of the frontend asking them for their details again. A
// guest sends no Authorization header; the request body then carries their phone number instead.
//
// NOTE: no backend endpoint for this exists yet (by design — the backend folder is not touched by
// this feature). Until one is added, the backend call below 404s and the caller sees a real,
// non-faked error toast; nothing here claims a save that didn't happen.
const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";

export async function POST(request) {
  const body = await request.text();
  const store = await cookies();
  const access = store.get("access_token")?.value;

  const headers = { Accept: "application/json", "Content-Type": "application/json" };
  if (access) headers.Authorization = `Bearer ${access}`;

  let res;
  try {
    res = await fetch(`${API_BASE_URL}/stock-notifications/`, { method: "POST", headers, body, cache: "no-store" });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
}
