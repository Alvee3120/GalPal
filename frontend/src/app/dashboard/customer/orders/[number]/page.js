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

// The backend's IsOwner permission (apps.accounts.permissions) already scopes MyOrderViewSet to the logged-in
// customer — a 404 here means either the order doesn't exist or, just as validly, it isn't this customer's, and
// the two are indistinguishable on purpose (matches how the same 404 already behaves for any other customer's
// order number, so this page can't be used to probe which order numbers exist).
export default async function CustomerOrderDetailPage({ params }) {
  const { number } = await params;
  const [order, currencySymbol] = await Promise.all([getOrder(number), getCurrencySymbol()]);
  if (!order) notFound();
  return <OrderDetail initialOrder={order} currencySymbol={currencySymbol} />;
}
