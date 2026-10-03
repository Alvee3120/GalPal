import { backendFetch } from "@/lib/backendAuth";
import SupportInbox from "@/component/dashboard/care/SupportInbox";

export const metadata = { title: "Support Inbox | GalPal" };

// Support inbox: contact form messages (Admin and CCE: served at /dashboard/CCE/… and, re-exported, /dashboard/admin/…; the backend's API is IsAdminOrCCE).
async function getInitial() {
  try {
    const res = await backendFetch("/admin/care/messages/?page_size=20");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  return <SupportInbox initial={await getInitial()} />;
}
