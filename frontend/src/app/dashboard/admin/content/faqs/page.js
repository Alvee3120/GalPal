import { backendFetch } from "@/lib/backendAuth";
import FaqManagement from "@/component/dashboard/content/FaqManagement";

export const metadata = { title: "FAQs | GalPal" };

// Questions on the storefront FAQ page (Admin only: this admin layout guards the route, and the backend's content API is IsAdmin).
async function getJson(path) {
  try {
    const res = await backendFetch(path);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  const faqs = await getJson("/admin/content/faqs/");
  return <FaqManagement initial={Array.isArray(faqs) ? faqs : []} />;
}
