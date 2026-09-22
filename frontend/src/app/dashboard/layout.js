import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/currentUser";
import DashboardShell from "@/component/dashboard/DashboardShell";

// Every /dashboard/* route is protected here: the EXISTING session (getCurrentUser -> GET /account/profile/,
// the same cookies Navbar/checkout already use) decides access, never a client-side check alone. No session ->
// straight to the existing login page. This layout renders the shared shell (sidebar/topbar, no footer — see
// FooterGate/Navbar's own "/dashboard" exclusion); a nested role-only branch (e.g. app/dashboard/customer/layout.js)
// does its own additional role check for routes only that role may see.
export default async function DashboardLayout({ children }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  // `navFor` is called inside DashboardShell (a Client Component), not here: its icons are React components
  // (functions), which can't be serialized across the server -> client boundary as a prop value.
  return <DashboardShell user={user}>{children}</DashboardShell>;
}
