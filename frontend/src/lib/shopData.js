import { parseCategories, SHOP_PAGE_SIZE } from "./shopQuery";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;
const DEFAULT_PRICE_BOUNDS = { min: 0, max: 10000 }; // fallback if the bounds lookup below fails

// The whole visible category tree for the sidebar: top-level categories, each with its nested `children` (the backend's
// /categories/tree/, one unpaginated response). A parent's `category` filter value already covers its sub-categories too.
export async function getShopCategories() {
  try {
    const res = await fetch(`${API_BASE_URL}/categories/tree/`, { next: { revalidate: REVALIDATE_SECONDS } });
    if (!res.ok) throw new Error(`Categories API responded ${res.status}`);
    const tree = await res.json();
    return Array.isArray(tree) ? tree : [];
  } catch (error) {
    console.error("Failed to load shop categories:", error);
    return [];
  }
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

// Several categories at once. The backend's product `category` filter takes a single slug, so each selected category is
// fetched with the same other filters (all pages), the results are de-duplicated (a parent and its child overlap), then
// sorted and paged here the way the backend would: newest first by default; price by effective price; rating; popularity
// = best sellers first, then review count (the backend's own formula).
const popularity = (p) => (p.is_bestseller ? 1_000_000 : 0) + (Number(p.review_count) || 0);
const SORTERS = {
  price: (a, b) => Number(a.effective_price) - Number(b.effective_price),
  "-price": (a, b) => Number(b.effective_price) - Number(a.effective_price),
  rating: (a, b) => Number(b.average_rating) - Number(a.average_rating),
  popularity: (a, b) => popularity(b) - popularity(a),
};

async function fetchEveryPage(firstUrl) {
  const results = [];
  for (let url = firstUrl; url; ) {
    const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
    if (!res.ok) throw new Error(`Products API responded ${res.status}`);
    const data = await res.json();
    results.push(...(data.results ?? []));
    url = data.next;
  }
  return results;
}

async function getProductsInCategories(searchParams, slugs) {
  const page = Math.max(1, Number(searchParams.page) || 1);
  try {
    const lists = await Promise.all(
      slugs.map((slug) => {
        const { url } = buildProductsUrl({ ...searchParams, category: slug, page: undefined, ordering: undefined });
        const full = new URL(url);
        full.searchParams.set("page_size", "100"); // the API's maximum page size
        return fetchEveryPage(full.toString());
      }),
    );
    const merged = [...new Map(lists.flat().map((product) => [product.id, product])).values()];
    const sorter = SORTERS[searchParams.ordering];
    merged.sort((a, b) => (sorter?.(a, b) || 0) || b.id - a.id);
    const start = (page - 1) * SHOP_PAGE_SIZE;
    return { products: merged.slice(start, start + SHOP_PAGE_SIZE), count: merged.length, page, error: false };
  } catch (error) {
    console.error("Failed to load shop products:", error);
    return { products: [], count: 0, page, error: true };
  }
}

export async function getShopProducts(searchParams) {
  const slugs = parseCategories(searchParams.category);
  if (slugs.length > 1) return getProductsInCategories(searchParams, slugs);
  const { url, page } = buildProductsUrl({ ...searchParams, category: slugs[0] });
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
