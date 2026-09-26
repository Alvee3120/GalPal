import VideoProductCarousel from "./VideoProductCarousel";
import NotifyOnMount from "@/component/shared/NotifyOnMount";
import { getCurrencySymbol } from "@/lib/siteSettings";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;
const MAX_PRODUCT_PAGES = 5; // safety cap while looking up prices

// How long each product stays visible before the next one of the same video slides in (ms).
export const PRODUCT_ROTATION_INTERVAL = 4000;

// A direct video file can play in <video>; a page URL (e.g. YouTube) cannot, so those show the thumbnail instead.
const isDirectVideo = (url) => typeof url === "string" && /\.(mp4|webm|mov|m4v|ogv)(\?.*)?$/i.test(url);

async function getJson(url) {
  // Tagged "videos": Video Card Management (app/api/admin/videos) revalidates it after every change.
  const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS, tags: ["videos"] } });
  if (!res.ok) throw new Error(`API responded ${res.status} for ${url}`);
  return res.json();
}

// GET /videos/: the backend's "video cards". Each carries its own linked products (published only) as
// { id, name, slug, image, price }, so the video <-> product pairing comes straight from the API.
async function getVideoCards(limit) {
  const cards = [];
  let url = `${API_BASE_URL}/videos/?page_size=${limit}`;
  while (url && cards.length < limit) {
    const data = await getJson(url);
    cards.push(...(data.results ?? []));
    url = data.next;
  }
  return cards.slice(0, limit);
}

// The video card's product summary only has one `price`. The existing GET /products/ list also carries the
// original price, discount and stock, so linked products are enriched by id (best effort: if this lookup fails,
// the cards simply fall back to the summary data).
async function getProductsById(ids) {
  const found = new Map();
  if (ids.size === 0) return found;
  try {
    let url = `${API_BASE_URL}/products/?page_size=100`;
    for (let page = 0; url && page < MAX_PRODUCT_PAGES && found.size < ids.size; page++) {
      const data = await getJson(url);
      for (const product of data.results ?? []) if (ids.has(product.id)) found.set(product.id, product);
      url = data.next;
    }
  } catch (error) {
    console.error("Failed to enrich video products:", error);
  }
  return found;
}

// Product shape the shared ProductCard expects (the /products/ list shape), built from the video's summary + list data.
function toCardProduct(summary, full) {
  return {
    id: summary.id,
    name: summary.name,
    slug: summary.slug,
    feature_image: full?.feature_image ?? summary.image ?? null,
    effective_price: full?.effective_price ?? summary.price,
    regular_price: full?.regular_price ?? summary.price,
    discount_percentage: full?.discount_percentage ?? 0,
    on_sale: full?.on_sale ?? false,
    in_stock: full?.in_stock ?? true,
    brand: full?.brand ?? null,
    primary_category: full?.primary_category ?? null,
  };
}

const sectionClass = "mx-auto w-full max-w-7xl px-4 py-7 sm:px-6 md:py-10 lg:px-8";

// Same footprint as the real carousel (video block + product row per item) so the page does not jump.
export function VideoCarouselSkeleton({ count = 5 }) {
  return (
    <section aria-label="Loading videos" aria-busy="true" className={sectionClass}>
      <div className="mb-8 md:mb-10">
        <div className="product-skeleton__line h-9 w-64 max-w-full animate-pulse rounded-full sm:h-11" />
        <div className="product-skeleton__line mt-4 h-4 w-72 max-w-full animate-pulse rounded-full" />
      </div>
      <ul className="vc-track vc-track--static">
        {Array.from({ length: count }, (_, i) => (
          <li key={i} className="vc-item">
            <div className="product-skeleton__line vc-video aspect-[9/16] animate-pulse" />
            <div className="vc-slot mt-3">
              <div className="product-card product-card--compact flex h-full items-center gap-3 p-2.5">
                <div className="product-skeleton__line h-14 w-14 shrink-0 animate-pulse rounded-xl sm:h-16 sm:w-16" />
                <div className="min-w-0 flex-1">
                  <div className="product-skeleton__line h-4 w-3/4 animate-pulse rounded-full" />
                  <div className="product-skeleton__line mt-2 h-4 w-1/3 animate-pulse rounded-full" />
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

// Reusable homepage section: shoppable videos, each with its related product(s) right underneath.
// Everything comes from the backend (GET /videos/ + product prices from GET /products/); no fake or static data.
//   title / description  section header
//   videoLimit           most videos fetched
//   autoScrollMs         how often the row advances by one video when it overflows (0 turns that off)
//   productRotateMs      how often each video’s product container switches to that video’s next product (0 = never)
export default async function ShoppableVideoCarousel({
  title = "Trending Beauty",
  description = "Discover products worth adding to your ritual.",
  videoLimit = 12,
  autoScrollMs = 4500,
  productRotateMs = PRODUCT_ROTATION_INTERVAL,
}) {
  let cards;
  try {
    cards = await getVideoCards(videoLimit);
  } catch (error) {
    console.error("Failed to load shoppable videos:", error);
    return <NotifyOnMount message="Unable to load videos." />;
  }
  if (cards.length === 0) return null; // nothing to show: hide the section entirely

  const ids = new Set(cards.flatMap((card) => (card.products ?? []).map((p) => p.id)));
  const [fullById, currencySymbol] = await Promise.all([getProductsById(ids), getCurrencySymbol()]);

  const items = cards.map((card) => ({
    id: card.id,
    title: card.title,
    videoUrl: isDirectVideo(card.video_url) ? card.video_url : null,
    thumbnail: card.thumbnail ?? null,
    products: (card.products ?? []).map((p) => toCardProduct(p, fullById.get(p.id))),
  }));

  return (
    <section aria-label={title} className={sectionClass}>
      <VideoProductCarousel items={items} currencySymbol={currencySymbol} title={title} description={description} autoScrollMs={autoScrollMs} productRotateMs={productRotateMs} />
    </section>
  );
}
