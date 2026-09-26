import Link from "next/link";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CouponForm from "@/component/dashboard/coupons/CouponForm";

export const metadata = { title: "Add Coupon | GalPal" };

export default async function AdminAddCouponPage() {
  const currencySymbol = await getCurrencySymbol();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/admin/coupons" className="showcase-muted text-sm hover:underline">
          &larr; Coupons
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Add Coupon</h1>
      </div>
      <CouponForm currencySymbol={currencySymbol} />
    </div>
  );
}
