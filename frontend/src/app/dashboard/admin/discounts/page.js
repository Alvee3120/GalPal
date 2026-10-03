import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import DiscountManagement from "@/component/dashboard/discounts/DiscountManagement";

export const metadata = { title: "Discounts | GalPal" };

// First page from GET /admin/discounts/ (IsAdmin; the admin-only layout guards this route too).
async function getDiscounts() {
  try {
    const res = await backendFetch("/admin/discounts/?page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function AdminDiscountsPage() {
  const [{ results, count }, currencySymbol] = await Promise.all([getDiscounts(), getCurrencySymbol()]);
  return <DiscountManagement initialDiscounts={results} initialCount={count} currencySymbol={currencySymbol} />;
}
