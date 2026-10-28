import { backendFetch } from "@/lib/backendAuth";
import MegaMenuBannerManagement from "@/component/dashboard/banners/MegaMenuBannerManagement";

export const metadata = { title: "Mega Menu Banners | GalPal" };

// Mega Menu Banners (Admin only: this admin layout guards the route, and /admin/mega-menu-banners/ is IsAdmin).
async function getBanners() {
  try {
    const res = await backendFetch("/admin/mega-menu-banners/");
    if (!res.ok) return null;
    const data = await res.json();
    return Array.isArray(data) ? data : (data.results ?? []);
  } catch {
    return null;
  }
}

export default async function AdminMegaMenuBannersPage() {
  return <MegaMenuBannerManagement initialBanners={await getBanners()} />;
}
