import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import OldCartDetail from "@/component/dashboard/oldCarts/OldCartDetail";

export const metadata = { title: "Old Cart | GalPal" };

// One customer's current cart (GET /admin/orders/old-carts/<id>/, IsAdminOrCCE). A 404 means it's no longer old
// (checked out, emptied, or the old items were removed).
async function getCart(id) {
  try {
    const res = await backendFetch(`/admin/orders/old-carts/${encodeURIComponent(id)}/`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function OldCartPage({ params }) {
  const { id } = await params;
  const [data, currencySymbol] = await Promise.all([getCart(id), getCurrencySymbol()]);
  if (!data) notFound();
  return <OldCartDetail data={data} currencySymbol={currencySymbol} />;
}
