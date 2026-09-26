import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CouponDetails from "@/component/dashboard/coupons/CouponDetails";

export const metadata = { title: "Coupon | GalPal" };

export default async function CceCouponPage({ params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const [res, currencySymbol] = await Promise.all([backendFetch(`/admin/coupons/${id}/`), getCurrencySymbol()]);
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`Unable to load coupon ${id}`);
  return <CouponDetails coupon={await res.json()} currencySymbol={currencySymbol} />;
}
