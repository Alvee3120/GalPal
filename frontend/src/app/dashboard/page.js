import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/currentUser";
import { backendFetch } from "@/lib/backendAuth";
import CustomerDashboardHome from "@/component/dashboard/CustomerDashboardHome";
import StaffDashboardHome from "@/component/dashboard/StaffDashboardHome";

export const metadata = { title: "Dashboard | GalPal" };

async function getOrderCount() {
  try {
    const res = await backendFetch("/orders/?page_size=1");
    if (!res.ok) return 0;
    const data = await res.json();
    return data.count ?? 0;
  } catch {
    return 0;
  }
}

// The role-aware /dashboard home (the layout above already guarantees a real, authenticated user).
export default async function DashboardHomePage() {
  const user = await getCurrentUser();
  // The layout above already requires a session for every real request; this guards the same case Next.js's
  // build-time prerendering hits (no request/cookies exist yet), so the page never dereferences a null user.
  if (!user) redirect("/login");
  if (user.role === "customer") {
    const orderCount = await getOrderCount();
    return <CustomerDashboardHome user={user} orderCount={orderCount} />;
  }
  return <StaffDashboardHome user={user} />;
}
