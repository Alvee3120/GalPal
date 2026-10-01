import { notFound } from "next/navigation";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import CustomerCareProfile from "@/component/dashboard/care/CustomerCareProfile";

export const metadata = { title: "Customer Profile | GalPal" };

async function getJson(path) {
  try {
    const res = await backendFetch(path);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// One customer's care profile (GET /admin/care/customers/<id>/, IsAdmin). 404 for staff accounts or unknown ids.
export default async function CustomerProfilePage({ params }) {
  const { id } = await params;
  const [profile, tags, currencySymbol] = await Promise.all([
    getJson(`/admin/care/customers/${encodeURIComponent(id)}/`),
    getJson("/admin/care/tags/"),
    getCurrencySymbol(),
  ]);
  if (!profile) notFound();
  return <CustomerCareProfile initial={profile} currencySymbol={currencySymbol} tagOptions={Array.isArray(tags) ? tags : []} />;
}
