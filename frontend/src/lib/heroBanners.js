const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;
// Cache tag for the homepage hero; the admin Hero Banners proxy revalidates it after every change.
export const HERO_BANNERS_TAG = "hero-banners";

// GET /hero-banners/ (apps.banners, public): the slider config and ONLY the banners visible now — active and within
// their schedule — already in display order, each with desktop/tablet/mobile image URLs (tablet and mobile fall back
// to the desktop image). Returns null when the API can't be reached, so the homepage can fall back gracefully.
export async function getHeroSlider() {
  try {
    const res = await fetch(`${API_BASE_URL}/hero-banners/`, {
      next: { revalidate: REVALIDATE_SECONDS, tags: [HERO_BANNERS_TAG] },
    });
    if (!res.ok) throw new Error(`Hero banners API responded ${res.status}`);
    const data = await res.json();
    return { config: data.config ?? {}, banners: (data.banners ?? []).filter((b) => b.desktop_image) };
  } catch (error) {
    console.error("Failed to load hero banners:", error);
    return null;
  }
}
