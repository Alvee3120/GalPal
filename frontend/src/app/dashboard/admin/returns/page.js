import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import ReturnRequests from "@/component/dashboard/care/ReturnRequests";

export const metadata = { title: "Return Requests | GalPal" };

// Customers' return / refund requests (Admin only: this admin layout guards the route, and the backend's care API is IsAdmin).
async function getInitial() {
  try {
    const res = await backendFetch("/admin/care/returns/?page_size=20");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  const [initial, currencySymbol] = await Promise.all([getInitial(), getCurrencySymbol()]);
  return <ReturnRequests initial={initial} currencySymbol={currencySymbol} />;
}
