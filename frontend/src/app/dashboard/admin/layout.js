import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/currentUser";

// The Admin section: the shared staff pages (re-exported from app/dashboard/CCE/) at /dashboard/admin/…. Admin only; the
// backend's own permissions (IsAdmin / IsCatalogStaff / IsAdminOrCCE) remain the real authorization for every call.
export default async function AdminDashboardLayout({ children }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "admin") redirect("/dashboard");
  return children;
}
