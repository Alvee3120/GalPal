import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import AbandonedCheckouts from "@/component/dashboard/care/AbandonedCheckouts";

export const metadata = { title: "Abandoned Checkouts | GalPal" };

// Checkouts with a name + phone but no order (Admin and CCE: served at /dashboard/CCE/… and, re-exported, /dashboard/admin/…; the backend's API is IsAdminOrCCE).
async function getInitial() {
  try {
    const res = await backendFetch("/admin/care/abandoned-checkouts/?page_size=20");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  const [initial, currencySymbol] = await Promise.all([getInitial(), getCurrencySymbol()]);
  return <AbandonedCheckouts initial={initial} currencySymbol={currencySymbol} />;
}
