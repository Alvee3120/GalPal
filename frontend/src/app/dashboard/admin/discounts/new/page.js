import Link from "next/link";
import { getCurrencySymbol } from "@/lib/siteSettings";
import DiscountForm from "@/component/dashboard/discounts/DiscountForm";

export const metadata = { title: "Add Discount | GalPal" };

export default async function AdminAddDiscountPage() {
  const currencySymbol = await getCurrencySymbol();
  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link href="/dashboard/admin/discounts" className="showcase-muted text-sm hover:underline">
          &larr; Discounts
        </Link>
        <h1 className="custom-font mt-2 text-2xl sm:text-3xl">Add Discount</h1>
      </div>
      <DiscountForm currencySymbol={currencySymbol} />
    </div>
  );
}
