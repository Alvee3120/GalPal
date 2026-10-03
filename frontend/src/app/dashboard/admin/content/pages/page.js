import { backendFetch } from "@/lib/backendAuth";
import ContentPages from "@/component/dashboard/content/ContentPages";

export const metadata = { title: "Content Pages | GalPal" };

// About, policy and custom storefront pages (Admin only: this admin layout guards the route, and the backend's content API is IsAdmin).
async function getJson(path) {
  try {
    const res = await backendFetch(path);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function Page() {
  const [pages, standard] = await Promise.all([getJson("/admin/content/pages/"), getJson("/admin/content/pages/standard/")]);
  return <ContentPages initial={Array.isArray(pages) ? pages : []} standardTitles={standard ?? {}} />;
}
