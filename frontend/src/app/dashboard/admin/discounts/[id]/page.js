import Link from "next/link";
import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import DiscountForm from "@/component/dashboard/discounts/DiscountForm";

export const metadata = { title: "Edit Discount | GalPal" };

export default async function AdminEditDiscountPage({ params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const [res, currencySymbol] = await Promise.all([backendFetch(`/admin/discounts/${id}/`), getCurrencySymbol()]);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Unable to load discount ${id}`);
  const discount = await res.json();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/admin/discounts" className="showcase-muted text-sm hover:underline">
          &larr; Discounts
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Edit Discount</h1>
        <p className="showcase-muted mt-1 text-sm">{discount.name}</p>
      </div>
      <DiscountForm key={`${discount.id}-${discount.updated_at}`} discount={discount} currencySymbol={currencySymbol} />
    </div>
  );
}
