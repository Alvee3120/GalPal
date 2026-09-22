import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/currentUser";

// Extra guard for the customer-only branch: the outer /dashboard layout already requires a real session, this
// additionally requires role === "customer" (an admin/CCE account is sent back to the shared dashboard home
// rather than merely having the link hidden from them — the sidebar not showing a link is never the only defense).
export default async function CustomerDashboardLayout({ children }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (user.role !== "customer") redirect("/dashboard");
  return children;
}
