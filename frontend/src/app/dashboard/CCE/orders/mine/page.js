import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import OrdersList from "@/component/dashboard/OrdersList";

export const metadata = { title: "My Orders | GalPal" };

async function getMyOrders() {
  try {
    const res = await backendFetch("/orders/?page_size=50");
    if (!res.ok) return [];
    const data = await res.json();
    return data.results ?? [];
  } catch {
    return [];
  }
}

// The CCE account's OWN orders (apps.orders.views.MyOrderViewSet, IsOwner-scoped to request.user — role-agnostic,
// the exact same endpoint the customer "My Orders" page uses) — deliberately NOT the customer orders CCE manages
// on the "Dashboard" order-management page, which is a different API (/admin/orders/) with different permissions.
export default async function CceMyOrdersPage() {
  const [orders, currencySymbol] = await Promise.all([getMyOrders(), getCurrencySymbol()]);
  return (
    <div className="flex flex-col gap-6">
      <h1 className="custom-font text-2xl sm:text-3xl">My Orders</h1>
      <OrdersList initialOrders={orders} currencySymbol={currencySymbol} basePath="/dashboard/CCE/orders/mine" />
    </div>
  );
}
