import BrandMarquee from "@/component/shared/BrandMarquee";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;

// Fetches every page of {API_BASE_URL}/brands/ and returns brands that have a logo.
async function getBrandLogos() {
  const logos = [];
  let url = `${API_BASE_URL}/brands/`;

  try {
    while (url) {
      const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
      if (!res.ok) throw new Error(`Brands API responded ${res.status}`);
      const data = await res.json();

      for (const brand of data.results ?? []) {
        if (brand.logo) {
          logos.push({ src: brand.logo, alt: `${brand.name} logo` });
        }
      }
      url = data.next;
    }
  } catch (error) {
    console.error("Failed to load brands:", error);
    return [];
  }

  return logos;
}

export default async function Marquee() {
  const logos = await getBrandLogos();
  // Logos come from the backend (possibly a private/local host), so skip
  // Next's image optimizer, which refuses to fetch from private IPs.
  return <BrandMarquee logos={logos} unoptimized />;
}
