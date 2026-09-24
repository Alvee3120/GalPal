import Link from "next/link";
import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import CategoryForm from "@/component/dashboard/categories/CategoryForm";

export const metadata = { title: "Edit Category | GalPal" };

export default async function CceEditCategoryPage({ params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const res = await backendFetch(`/admin/categories/${id}/`);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Unable to load category ${id}`);
  const category = await res.json();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/CCE/categories" className="showcase-muted text-sm hover:underline">
          &larr; Category Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Edit Category</h1>
        <p className="showcase-muted mt-1 text-sm">{category.name}</p>
      </div>
      <CategoryForm key={`${category.id}-${category.updated_at}`} category={category} />
    </div>
  );
}
