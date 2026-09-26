import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/currentUser";

// Extra guard for the CCE-only branch, mirroring app/dashboard/customer/layout.js: the outer /dashboard layout
// already requires a real session, this additionally requires role === "cce" — anyone else is sent back to the
// dashboard home rather than merely having the links hidden from them. Admin reaches the same pages at
// /dashboard/admin/… (app/dashboard/admin/layout.js). The backend's own
// IsAdminOrCCE (apps.accounts.permissions) is the actual authorization boundary for every API call these pages
// make; this is defense in depth, not the source of truth.
export default async function CceDashboardLayout({ children }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "cce") redirect("/dashboard");
  return children;
}
