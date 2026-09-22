// Server-side reads of the existing reviews API (same fetch-direct-from-backend pattern as shopData.js/getProduct —
// these run in Server Components, so the backend URL never needs to reach the browser).
const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
export const REVIEWS_PAGE_SIZE = 5;

// A product's first page of APPROVED reviews, newest first (GET /reviews/?product=<slug>, paginated
// {count, next, previous, results} — the backend's standard page-number shape).
export async function getProductReviews(slug) {
  try {
    const res = await fetch(`${API_BASE_URL}/reviews/?product=${encodeURIComponent(slug)}&page_size=${REVIEWS_PAGE_SIZE}`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) throw new Error(`Reviews API responded ${res.status}`);
    const data = await res.json();
    return { results: data.results ?? [], count: data.count ?? 0, hasMore: Boolean(data.next) };
  } catch (error) {
    console.error("Failed to load reviews:", error);
    return { results: [], count: 0, hasMore: false };
  }
}

// A product's rating breakdown (GET /reviews/breakdown/?product=<slug>): the authoritative average, count and
// per-star counts — the same numbers the product's own average_rating/review_count reflect, just with the bars.
export async function getRatingBreakdown(slug) {
  try {
    const res = await fetch(`${API_BASE_URL}/reviews/breakdown/?product=${encodeURIComponent(slug)}`, { next: { revalidate: 30 } });
    if (!res.ok) throw new Error(`Rating breakdown API responded ${res.status}`);
    return await res.json();
  } catch (error) {
    console.error("Failed to load rating breakdown:", error);
    return { average_rating: "0.00", review_count: 0, breakdown: { 5: 0, 4: 0, 3: 0, 2: 0, 1: 0 } };
  }
}
