import { getCurrencySymbol } from "@/lib/siteSettings";
import AddOrderForm from "@/component/dashboard/AddOrderForm";

export const metadata = { title: "Add Order | GalPal" };

export default async function CceAddOrderPage() {
  const currencySymbol = await getCurrencySymbol();
  return (
    <div className="flex flex-col gap-6">
      <h1 className="custom-font text-2xl sm:text-3xl">Add Order</h1>
      <AddOrderForm currencySymbol={currencySymbol} />
    </div>
  );
}
