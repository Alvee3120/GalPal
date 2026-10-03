import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import OldCartsList from "@/component/dashboard/oldCarts/OldCartsList";

export const metadata = { title: "Old Carts | GalPal" };

// Old Carts for Admin and CCE (served at /dashboard/CCE/… and, re-exported, /dashboard/admin/…):
// GET /admin/orders/old-carts/ (IsAdminOrCCE) — customers whose cart has held an item for more than 6 hours.
async function getOldCarts() {
  try {
    const res = await backendFetch("/admin/orders/old-carts/?page_size=20");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function OldCartsPage() {
  const [initial, currencySymbol] = await Promise.all([getOldCarts(), getCurrencySymbol()]);
  return <OldCartsList initial={initial} currencySymbol={currencySymbol} />;
}
