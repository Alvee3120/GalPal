import { revalidateTag } from "next/cache";
import { backendFetch } from "@/lib/backendAuth";
import { SITE_SETTINGS_TAG } from "@/lib/siteSettings";
import { SITE_SETTINGS_KEYS, pickSiteSettings } from "@/lib/siteSettingsAdmin";

// Proxy to the EXISTING Site Settings admin API (PATCH /admin/site-settings/, IsAdmin — CCE and customers get 403
// there). Narrowed to what the dashboard's Site Settings page edits; anything else in the body is dropped. A save
// refreshes the cached public settings, so the footer (and invoices) show the new details on their next render.
const ALLOWED = new Set(SITE_SETTINGS_KEYS);

export async function PATCH(request) {
  const incoming = (await request.json().catch(() => null)) ?? {};
  const body = Object.fromEntries(Object.entries(incoming).filter(([key]) => ALLOWED.has(key)));
  let res;
  try {
    res = await backendFetch("/admin/site-settings/", { method: "PATCH", body: JSON.stringify(body) });
  } catch {
    return Response.json({ error: { message: "We couldn't reach the server." } }, { status: 502 });
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) return Response.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
  revalidateTag(SITE_SETTINGS_TAG, { expire: 0 });
  return Response.json(pickSiteSettings(data), { headers: { "Cache-Control": "no-store" } });
}
