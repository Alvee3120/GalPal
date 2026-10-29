const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;
// Cache tag for the Shop mega menu; the admin Mega Menu proxy revalidates it after every change.
export const MEGA_MENU_TAG = "mega-menu";

// GET /mega-menu/banners/ (apps.banners, public): the active Shop mega menu images by slot — "square_1",
// "square_2" and "wide" — already filtered to active ones. Returns [] when the API can't be reached.
export async function getMegaMenuBanners() {
  try {
    const res = await fetch(`${API_BASE_URL}/mega-menu/banners/`, {
      next: { revalidate: REVALIDATE_SECONDS, tags: [MEGA_MENU_TAG] },
    });
    if (!res.ok) throw new Error(`Mega menu banners API responded ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error("Failed to load mega menu banners:", error);
    return [];
  }
}

// GET /brands/ (apps.catalog, public — active brands only): the mega menu's brand column (state 1). One page of 100
// covers the whole list for a shop this size; anything longer can be reached through the Shop page's brand search.
export async function getMegaMenuBrands() {
  try {
    const res = await fetch(`${API_BASE_URL}/brands/?page_size=100`, {
      next: { revalidate: REVALIDATE_SECONDS, tags: [MEGA_MENU_TAG] },
    });
    if (!res.ok) throw new Error(`Brands API responded ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : (data.results ?? []);
  } catch (error) {
    console.error("Failed to load mega menu brands:", error);
    return [];
  }
}
