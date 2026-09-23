import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CceOrderDetail from "@/component/dashboard/CceOrderDetail";

export const metadata = { title: "Manage Order | GalPal" };

async function getOrder(id) {
  try {
    const res = await backendFetch(`/admin/orders/${encodeURIComponent(id)}/`);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(`Admin orders API responded ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error("Failed to load order:", error);
    return null;
  }
}

// A customer order a CCE/Admin is authorized to manage (apps.orders.views_admin.AdminOrderViewSet, IsAdminOrCCE —
// the backend rejects anything this account can't reach; a 404 here just means the id doesn't exist).
export default async function CceOrderManagePage({ params }) {
  const { id } = await params;
  const [order, currencySymbol] = await Promise.all([getOrder(id), getCurrencySymbol()]);
  if (!order) notFound();
  return <CceOrderDetail initialOrder={order} currencySymbol={currencySymbol} />;
}
