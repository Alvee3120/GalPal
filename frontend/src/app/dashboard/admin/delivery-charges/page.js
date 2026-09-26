import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import DeliveryChargeSettings from "@/component/dashboard/DeliveryChargeSettings";

export const metadata = { title: "Delivery Charges | GalPal" };

// The delivery zones and their charges (GET /admin/shipping/zones/, IsAdmin; the admin-only layout guards this route).
async function getZones() {
  try {
    const res = await backendFetch("/admin/shipping/zones/?page_size=100&ordering=sort_order");
    if (!res.ok) return null;
    const data = await res.json();
    return Array.isArray(data) ? data : (data.results ?? []);
  } catch {
    return null;
  }
}

export default async function AdminDeliveryChargesPage() {
  const [zones, currencySymbol] = await Promise.all([getZones(), getCurrencySymbol()]);
  return <DeliveryChargeSettings initialZones={zones} currencySymbol={currencySymbol} />;
}
