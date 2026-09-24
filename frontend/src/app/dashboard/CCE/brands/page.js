import { backendFetch } from "@/lib/backendAuth";
import CceBrandManagement from "@/component/dashboard/brands/CceBrandManagement";

export const metadata = { title: "Brand Management | GalPal" };

// First page server-side from the EXISTING /admin/brands/ list; search and paging then run client-side.
async function getBrands() {
  try {
    const res = await backendFetch("/admin/brands/?page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function CceBrandsPage() {
  const { results, count } = await getBrands();
  return <CceBrandManagement initialBrands={results} initialCount={count} />;
}
