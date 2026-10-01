import { backendFetch } from "@/lib/backendAuth";
import MessageTemplates from "@/component/dashboard/notifications/MessageTemplates";

export const metadata = { title: "Message Templates | GalPal" };

// Email/SMS templates (Admin only: this admin layout guards the route, and the backend's notifications API is IsAdmin).
async function getTemplates() {
  try {
    const res = await backendFetch("/admin/notifications/templates/");
    return res.ok ? await res.json() : [];
  } catch {
    return [];
  }
}

export default async function Page() {
  const templates = await getTemplates();
  return <MessageTemplates initial={Array.isArray(templates) ? templates : []} />;
}
