import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CceOrderManagement from "@/component/dashboard/CceOrderManagement";

export const metadata = { title: "Order Management | GalPal" };

// Order Management: the customer orders a CCE works (apps.orders.views_admin.AdminOrderViewSet, IsAdminOrCCE). Its
// own page — /dashboard is the analytics overview.
async function getManagedOrders() {
  try {
    const res = await backendFetch("/admin/orders/?page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function CceOrdersPage() {
  const [{ results, count }, currencySymbol] = await Promise.all([getManagedOrders(), getCurrencySymbol()]);
  return <CceOrderManagement initialOrders={results} initialCount={count} currencySymbol={currencySymbol} />;
}
