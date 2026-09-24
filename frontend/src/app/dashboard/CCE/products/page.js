import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CceProductManagement from "@/component/dashboard/products/CceProductManagement";

export const metadata = { title: "Product Management | GalPal" };

// First page server-side (the EXISTING /admin/products/ list, IsCatalogStaff); search and paging then run in the
// client component through the /api/admin/catalog proxy.
async function getProducts() {
  try {
    const res = await backendFetch("/admin/products/?page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function CceProductsPage() {
  const [{ results, count }, currencySymbol] = await Promise.all([getProducts(), getCurrencySymbol()]);
  return <CceProductManagement initialProducts={results} initialCount={count} currencySymbol={currencySymbol} />;
}
