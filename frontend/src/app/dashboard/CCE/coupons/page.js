import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CouponManagement from "@/component/dashboard/coupons/CouponManagement";

export const metadata = { title: "Coupons | GalPal" };

// CCE: the same coupons Admin manages (GET /admin/coupons/ — read-only for CCE backend-side), without Add/Edit/Delete.
async function getCoupons() {
  try {
    const res = await backendFetch("/admin/coupons/?page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function CceCouponsPage() {
  const [{ results, count }, currencySymbol] = await Promise.all([getCoupons(), getCurrencySymbol()]);
  return <CouponManagement initialCoupons={results} initialCount={count} currencySymbol={currencySymbol} readOnly />;
}
