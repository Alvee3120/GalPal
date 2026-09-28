import { backendFetch } from "@/lib/backendAuth";
import { pickSiteSettings } from "@/lib/siteSettingsAdmin";
import SiteSettingsForm from "@/component/dashboard/SiteSettingsForm";

export const metadata = { title: "Site Settings | GalPal" };

// Site Settings (Admin only: this admin layout guards the route, and GET/PATCH /admin/site-settings/ is IsAdmin).
// Reads the live row, not the cached public copy.
async function getSettings() {
  try {
    const res = await backendFetch("/admin/site-settings/");
    return res.ok ? pickSiteSettings(await res.json()) : null;
  } catch {
    return null;
  }
}

export default async function AdminSiteSettingsPage() {
  return <SiteSettingsForm initial={await getSettings()} />;
}
