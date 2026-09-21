// Shared between the Shop page (server) and its filter controls (client): the URL's query string is the
// single source of truth for every filter, so the grid, the active-filter tags and Clear All are just links.
export const SHOP_PAGE_SIZE = 12;

export const SORT_OPTIONS = [
  { value: "", label: "Default Sorting" },
  { value: "price", label: "Price: Low to High" },
  { value: "-price", label: "Price: High to Low" },
  { value: "newest", label: "Newest" },
  { value: "rating", label: "Top Rated" },
  { value: "popularity", label: "Popularity" },
];

export const PROMOTIONS = [
  { param: "is_new_arrival", label: "New Arrivals" },
  { param: "is_bestseller", label: "Best Sellers" },
  { param: "on_sale", label: "On Sale" },
];

// Query keys for the actual *filters* (not sorting/paging) — drives the mobile filter-count badge.
export const FILTER_KEYS = ["category", "price_min", "price_max", "is_new_arrival", "is_bestseller", "on_sale", "in_stock"];

// Builds "?key=value&..." from a plain searchParams object plus a set of changes. Setting a key to
// null/undefined/"" removes it. Any change other than paging alone resets `page` back to 1.
export function buildShopHref(searchParams, changes) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries({ ...searchParams, ...changes })) {
    if (value === null || value === undefined || value === "") continue;
    params.set(key, String(value));
  }
  const onlyPage = Object.keys(changes).length === 1 && "page" in changes;
  if (!onlyPage) params.delete("page");
  const qs = params.toString();
  return qs ? `/shop?${qs}` : "/shop";
}
