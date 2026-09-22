import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/currentUser";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CustomerDashboardHome from "@/component/dashboard/CustomerDashboardHome";
import StaffDashboardHome from "@/component/dashboard/StaffDashboardHome";
import CceOrderManagement from "@/component/dashboard/CceOrderManagement";

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

async function getManagedOrders() {
  try {
    const res = await backendFetch("/admin/orders/?page_size=30");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

// The role-aware /dashboard home (the layout above already guarantees a real, authenticated user). For CCE,
// "Dashboard" IS the order-management view — the customer orders a CCE is authorized to work
// (apps.orders.views_admin.AdminOrderViewSet, IsAdminOrCCE) — since the nav has no separate entry for it.
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
    const [{ results, count }, currencySymbol] = await Promise.all([getManagedOrders(), getCurrencySymbol()]);
    return <CceOrderManagement initialOrders={results} initialCount={count} currencySymbol={currencySymbol} />;
  }
  return <StaffDashboardHome user={user} />;
}
