import ProductCarousel from "./ProductCarousel";
import { getCurrencySymbol } from "@/lib/siteSettings";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;

// The backend's `category` filter takes a category slug and already includes every sub-category,
// so a single request returns the parent's own products plus all of its children's.
// Pages are followed only if the backend caps page_size below `limit`.
async function getCategoryProducts({ category, limit, ordering }) {
  const products = new Map(); // keyed by id: a product can never appear twice
  const params = new URLSearchParams({ category, page_size: String(limit) });
  if (ordering) params.set("ordering", ordering);
  let url = `${API_BASE_URL}/products/?${params}`;

  try {
    while (url && products.size < limit) {
      const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
      if (!res.ok) throw new Error(`Products API responded ${res.status}`);
      const data = await res.json();
      for (const product of data.results ?? []) products.set(product.id, product);
      url = data.next;
    }
  } catch (error) {
    console.error(`Failed to load products for category "${category}":`, error);
    return { products: [], error: true };
  }

  return { products: [...products.values()].slice(0, limit), error: false };
}

const sectionClass = "mx-auto w-full max-w-7xl px-4 py-7 sm:px-6 md:py-10 lg:px-8";

function Message({ title, children }) {
  return (
    <div className={sectionClass}>
      <h2 className="custom-font text-3xl leading-tight sm:text-4xl">{title}</h2>
      <p className="showcase-muted mt-6 text-sm">{children}</p>
    </div>
  );
}

// Same footprint as the real carousel (same track, same tile shapes) so the page does not jump.
export function ProductShowcaseSkeleton({ columns = 4, rows = 1 }) {
  return (
    <section aria-label="Loading products" aria-busy="true" className={sectionClass}>
      <div className="mb-8 md:mb-10">
        <div className="product-skeleton__line h-9 w-64 max-w-full animate-pulse rounded-full sm:h-11" />
        <div className="product-skeleton__line mt-4 h-4 w-72 max-w-full animate-pulse rounded-full" />
      </div>
      <ul className="product-track product-track--static" style={{ "--pc-cols": columns, "--pc-rows": rows }}>
        {Array.from({ length: columns * rows }, (_, i) => (
          <li key={i} className="product-track__item min-w-0">
            <div className="product-card p-3 sm:p-4">
              <div className="product-skeleton__line aspect-square animate-pulse" style={{ borderRadius: "var(--radius-card)" }} />
              <div className="product-skeleton__line mt-4 h-4 w-3/4 animate-pulse rounded-full" />
              <div className="product-skeleton__line mt-2 h-4 w-1/3 animate-pulse rounded-full" />
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}


export default async function CategoryProductShowcase({
  category,
  title,
  description,
  productLimit = 8,
  columns = 4,
  rows = 1,
  ordering = "popularity",
}) {
  const [{ products, error }, currencySymbol] = await Promise.all([
    getCategoryProducts({ category, limit: productLimit, ordering }),
    getCurrencySymbol(),
  ]);

  if (error) return <Message title={title}>We couldn&apos;t load these products right now. Please try again shortly.</Message>;
  if (products.length === 0) return <Message title={title}>No products available yet.</Message>;

  return (
    <section aria-label={title} className={sectionClass}>
      <ProductCarousel
        products={products}
        currencySymbol={currencySymbol}
        title={title}
        description={description}
        columns={columns}
        rows={rows}
      />
    </section>
  );
}
