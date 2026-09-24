import { backendFetch } from "@/lib/backendAuth";
import StockNotificationList from "@/component/dashboard/StockNotificationList";

export const metadata = { title: "Notify Me Requests | GalPal" };

// First page (waiting requests) server-side from GET /admin/stock-notifications/; the rest runs client-side.
async function getWaiting() {
  try {
    const res = await backendFetch("/admin/stock-notifications/?status=waiting&page_size=10");
    if (!res.ok) return { results: [], count: 0 };
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0 };
  } catch {
    return { results: [], count: 0 };
  }
}

export default async function CceStockNotificationsPage() {
  const { results, count } = await getWaiting();
  return <StockNotificationList initialRows={results} initialCount={count} />;
}
