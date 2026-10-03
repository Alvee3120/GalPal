import { backendFetch } from "@/lib/backendAuth";
import AuditLog from "@/component/dashboard/audit/AuditLog";

export const metadata = { title: "Audit Log | GalPal" };

// The audit log, key events first (Admin only: this admin layout guards the route, and the backend's API is IsAdmin).
async function getInitial() {
  try {
    const res = await backendFetch("/admin/audit-logs/?kind=event&page_size=25");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  return <AuditLog initial={await getInitial()} />;
}
