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

// The `category` query param holds one or more category slugs, comma-separated ("serums,lips"); a single slug is just
// the one-item case, so existing links keep working.
export function parseCategories(value) {
  return String(value ?? "").split(",").map((slug) => slug.trim()).filter(Boolean);
}

// The `category` param value after adding/removing `slug` (null when none are left, which removes the param).
export function toggleCategoryParam(value, slug) {
  const current = parseCategories(value);
  const next = current.includes(slug) ? current.filter((s) => s !== slug) : [...current, slug];
  return next.length ? next.join(",") : null;
}

// Every category of the tree (parents and all nested children) as one flat list, e.g. to look a category up by slug.
export function flattenCategories(tree) {
  return tree.flatMap((category) => [category, ...flattenCategories(category.children ?? [])]);
}

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
