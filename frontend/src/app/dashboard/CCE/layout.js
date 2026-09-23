import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/currentUser";

// Extra guard for the CCE-only branch, mirroring app/dashboard/customer/layout.js: the outer /dashboard layout
// already requires a real session, this additionally requires role === "cce" — a customer or admin account is
// sent back to the shared dashboard home rather than merely having the link hidden from them. The backend's own
// IsAdminOrCCE (apps.accounts.permissions) is the actual authorization boundary for every API call these pages
// make; this is defense in depth, not the source of truth.
export default async function CceDashboardLayout({ children }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "cce") redirect("/dashboard");
  return children;
}
