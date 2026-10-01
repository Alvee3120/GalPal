import { backendFetch } from "@/lib/backendAuth";
import NotificationLog from "@/component/dashboard/notifications/NotificationLog";

export const metadata = { title: "Notifications | GalPal" };

// The notification log (Admin only: this admin layout guards the route, and the backend's notifications API is IsAdmin).
async function getInitial() {
  try {
    const res = await backendFetch("/admin/notifications/logs/?page_size=20");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  return <NotificationLog initial={await getInitial()} />;
}
