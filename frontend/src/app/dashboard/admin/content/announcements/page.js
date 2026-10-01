import { backendFetch } from "@/lib/backendAuth";
import AnnouncementManagement from "@/component/dashboard/content/AnnouncementManagement";

export const metadata = { title: "Announcements | GalPal" };

// The announcement bar above the storefront navbar (Admin only: this admin layout guards the route, and the backend's content API is IsAdmin).
async function getJson(path) {
  try {
    const res = await backendFetch(path);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  const items = await getJson("/admin/content/announcements/");
  return <AnnouncementManagement initial={Array.isArray(items) ? items : []} />;
}
