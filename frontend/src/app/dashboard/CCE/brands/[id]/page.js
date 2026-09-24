import Link from "next/link";
import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import BrandForm from "@/component/dashboard/brands/BrandForm";

export const metadata = { title: "Edit Brand | GalPal" };

export default async function CceEditBrandPage({ params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const res = await backendFetch(`/admin/brands/${id}/`);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Unable to load brand ${id}`);
  const brand = await res.json();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/CCE/brands" className="showcase-muted text-sm hover:underline">
          &larr; Brand Management
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Edit Brand</h1>
        <p className="showcase-muted mt-1 text-sm">{brand.name}</p>
      </div>
      <BrandForm key={`${brand.id}-${brand.updated_at}`} brand={brand} />
    </div>
  );
}
