import { backendFetch } from "@/lib/backendAuth";
import SupportInbox from "@/component/dashboard/care/SupportInbox";

export const metadata = { title: "Support Inbox | GalPal" };

// Support inbox: contact form messages (Admin only: this admin layout guards the route, and the backend's care API is IsAdmin).
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
