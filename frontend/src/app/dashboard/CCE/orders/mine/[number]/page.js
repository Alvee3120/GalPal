import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import OrderDetail from "@/component/dashboard/OrderDetail";

export const metadata = { title: "Order Details | GalPal" };

async function getOrder(number) {
  try {
    const res = await backendFetch(`/orders/${encodeURIComponent(number)}/`);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`Orders API responded ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error("Failed to load order:", error);
    return null;
  }
}

// Detail for one of the CCE account's OWN orders — same MyOrderViewSet-backed component as the customer page,
// just mounted here since /dashboard/customer/... is customer-only.
export default async function CceMyOrderDetailPage({ params }) {
  const { number } = await params;
  const [order, currencySymbol] = await Promise.all([getOrder(number), getCurrencySymbol()]);
  if (!order) notFound();
  return <OrderDetail initialOrder={order} currencySymbol={currencySymbol} />;
}
