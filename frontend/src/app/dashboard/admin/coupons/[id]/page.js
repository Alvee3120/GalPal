import Link from "next/link";
import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CouponForm from "@/component/dashboard/coupons/CouponForm";

export const metadata = { title: "Edit Coupon | GalPal" };

export default async function AdminEditCouponPage({ params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const [res, currencySymbol] = await Promise.all([backendFetch(`/admin/coupons/${id}/`), getCurrencySymbol()]);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Unable to load coupon ${id}`);
  const coupon = await res.json();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/admin/coupons" className="showcase-muted text-sm hover:underline">
          &larr; Coupons
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Edit Coupon</h1>
        <p className="showcase-muted mt-1 text-sm">
          <span className="font-mono font-semibold">{coupon.code}</span> · used {coupon.usage_count} time{coupon.usage_count === 1 ? "" : "s"}
        </p>
      </div>
      <CouponForm key={`${coupon.id}-${coupon.updated_at}`} coupon={coupon} currencySymbol={currencySymbol} />
    </div>
  );
}
