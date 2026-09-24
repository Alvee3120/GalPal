import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/currentUser";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CustomerDashboardHome from "@/component/dashboard/CustomerDashboardHome";
import StaffDashboardHome from "@/component/dashboard/StaffDashboardHome";
import CceDashboardOverview from "@/component/dashboard/overview/CceDashboardOverview";

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

async function getOverview() {
  try {
    const res = await backendFetch("/admin/orders/dashboard/");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// The role-aware /dashboard home (the layout above already guarantees a real, authenticated user). For CCE it's the
// analytics overview (GET /admin/orders/dashboard/, apps.orders.analytics); Order Management is its own page,
// /dashboard/CCE/orders.
export default async function DashboardHomePage() {
  const user = await getCurrentUser();
  // The layout above already requires a session for every real request; this guards the same case Next.js's
  // build-time prerendering hits (no request/cookies exist yet), so the page never dereferences a null user.
  if (!user) redirect("/login");
  if (user.role === "customer") {
    const orderCount = await getOrderCount();
    return <CustomerDashboardHome user={user} orderCount={orderCount} />;
  }
  if (user.role === "cce") {
    const [overview, currencySymbol] = await Promise.all([getOverview(), getCurrencySymbol()]);
    return <CceDashboardOverview initialData={overview} currencySymbol={currencySymbol} />;
  }
  return <StaffDashboardHome user={user} />;
}
