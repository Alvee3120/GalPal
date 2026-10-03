import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import AbandonedCheckouts from "@/component/dashboard/care/AbandonedCheckouts";

export const metadata = { title: "Abandoned Checkouts | GalPal" };

// Checkouts with a name + phone but no order (Admin only: this admin layout guards the route, and the backend's care API is IsAdmin).
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
