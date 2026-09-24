import { backendFetch } from "@/lib/backendAuth";
import CceCategoryManagement from "@/component/dashboard/categories/CceCategoryManagement";

export const metadata = { title: "Category Management | GalPal" };

async function getJson(path, fallback) {
  try {
    const res = await backendFetch(path);
    return res.ok ? await res.json() : fallback;
  } catch {
    return fallback;
  }
}

// First page + the tree (for parent names) server-side, from the EXISTING /admin/categories/ endpoints.
export default async function CceCategoriesPage() {
  const [list, tree] = await Promise.all([getJson("/admin/categories/?page_size=10", { results: [], count: 0 }), getJson("/admin/categories/tree/", [])]);
  return <CceCategoryManagement initialCategories={list.results ?? []} initialCount={list.count ?? 0} initialTree={tree} />;
}
