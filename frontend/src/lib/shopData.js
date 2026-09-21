import { SHOP_PAGE_SIZE } from "./shopQuery";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;
const DEFAULT_PRICE_BOUNDS = { min: 0, max: 10000 }; // fallback if the bounds lookup below fails

// Parent categories for the sidebar (their `category` filter value already covers their sub-categories too).
export async function getShopCategories() {
  const categories = [];
  let url = `${API_BASE_URL}/categories/?top_level=true`;
  try {
    while (url) {
      const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
      if (!res.ok) throw new Error(`Categories API responded ${res.status}`);
      const data = await res.json();
      categories.push(...(data.results ?? []).filter((c) => c.parent === null));
      url = data.next;
    }
  } catch (error) {
    console.error("Failed to load shop categories:", error);
  }
  return categories;
}

// The cheapest and most expensive in-stock product set the slider's bounds, instead of a guessed cap.
export async function getShopPriceBounds() {
  try {
    const [lowest, highest] = await Promise.all([
      fetch(`${API_BASE_URL}/products/?ordering=price&page_size=1`, { next: { revalidate: 300 } }).then((r) => (r.ok ? r.json() : null)),
      fetch(`${API_BASE_URL}/products/?ordering=-price&page_size=1`, { next: { revalidate: 300 } }).then((r) => (r.ok ? r.json() : null)),
    ]);
    const min = Number(lowest?.results?.[0]?.effective_price);
    const max = Number(highest?.results?.[0]?.effective_price);
    if (Number.isFinite(min) && Number.isFinite(max) && max > min) return { min: Math.floor(min), max: Math.ceil(max) };
  } catch (error) {
    console.error("Failed to load shop price bounds:", error);
  }
  return DEFAULT_PRICE_BOUNDS;
}

// Turns the Shop page's URL search params into the backend's GET /products/ filters.
function buildProductsUrl(searchParams) {
  const params = new URLSearchParams({ page_size: String(SHOP_PAGE_SIZE) });
  const page = Math.max(1, Number(searchParams.page) || 1);
  if (page > 1) params.set("page", String(page));
  if (searchParams.category) params.set("category", searchParams.category);
  if (searchParams.price_min) params.set("price_min", searchParams.price_min);
  if (searchParams.price_max) params.set("price_max", searchParams.price_max);
  if (searchParams.is_new_arrival === "true") params.set("is_new_arrival", "true");
  if (searchParams.is_bestseller === "true") params.set("is_bestseller", "true");
  if (searchParams.on_sale === "true") params.set("on_sale", "true");
  if (searchParams.in_stock === "true" || searchParams.in_stock === "false") params.set("in_stock", searchParams.in_stock);
  if (searchParams.ordering) params.set("ordering", searchParams.ordering);
  return { url: `${API_BASE_URL}/products/?${params}`, page };
}

export async function getShopProducts(searchParams) {
  const { url, page } = buildProductsUrl(searchParams);
  try {
    const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
    if (!res.ok) throw new Error(`Products API responded ${res.status}`);
    const data = await res.json();
    return { products: data.results ?? [], count: data.count ?? 0, page, error: false };
  } catch (error) {
    console.error("Failed to load shop products:", error);
    return { products: [], count: 0, page, error: true };
  }
}
