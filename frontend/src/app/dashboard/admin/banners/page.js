import { backendFetch } from "@/lib/backendAuth";
import HeroBannerManagement from "@/component/dashboard/banners/HeroBannerManagement";

export const metadata = { title: "Hero Banners | GalPal" };

// Hero Banners (Admin only: this admin layout guards the route, and GET /admin/hero-banners/ is IsAdmin).
async function getBanners() {
  try {
    const res = await backendFetch("/admin/hero-banners/?ordering=sort_order&page_size=10");
    if (!res.ok) return null;
    const data = await res.json();
    return Array.isArray(data) ? data : (data.results ?? []);
  } catch {
    return null;
  }
}

export default async function AdminHeroBannersPage() {
  return <HeroBannerManagement initialBanners={await getBanners()} />;
}
