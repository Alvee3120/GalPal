import { backendFetch } from "@/lib/backendAuth";
import HomepageSectionsManagement from "@/component/dashboard/content/HomepageSectionsManagement";

export const metadata = { title: "Homepage Sections | GalPal" };

// The homepage's category product sections (Admin only: this admin layout guards the route, and the backend's content
// API is IsAdmin).
async function getSections() {
  try {
    const res = await backendFetch("/admin/content/category-sections/");
    return res.ok ? await res.json() : [];
  } catch {
    return [];
  }
}

export default async function Page() {
  const sections = await getSections();
  return <HomepageSectionsManagement initial={Array.isArray(sections) ? sections : []} />;
}
