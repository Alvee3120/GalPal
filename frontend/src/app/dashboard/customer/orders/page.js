import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import OrdersList from "@/component/dashboard/OrdersList";

export const metadata = { title: "My Orders | GalPal" };

async function getMyOrders() {
  try {
    const res = await backendFetch("/orders/?page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function CustomerOrdersPage() {
  const [{ results, count }, currencySymbol] = await Promise.all([getMyOrders(), getCurrencySymbol()]);
  return (
    <div className="flex flex-col gap-6">
      <h1 className="custom-font text-2xl sm:text-3xl">My Orders</h1>
      <OrdersList initialOrders={results} initialCount={count} currencySymbol={currencySymbol} />
    </div>
  );
}
