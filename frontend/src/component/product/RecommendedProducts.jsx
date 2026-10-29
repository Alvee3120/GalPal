import ProductCard from "@/component/shared/ProductCard";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const RECOMMENDED_COUNT = 4;
const FALLBACK_PAGE_SIZE = 12;

// "Recommended For You" data. The backend's related products for this product come first (published items from the
// same primary category, excluding the product itself). When fewer than RECOMMENDED_COUNT are available we top up
// from the existing /products/ list endpoint, always dropping duplicates and the product itself, so the row holds
// four whenever the catalog has four eligible products. A failed top-up degrades to whatever we already have.
async function getRecommendedProducts(product) {
  const picked = [];
  const seen = new Set([product?.id]);
  const add = (item) => {
    if (item && !seen.has(item.id)) {
      seen.add(item.id);
      picked.push(item);
    }
  };

  (product?.related_products ?? []).forEach(add);

  if (picked.length < RECOMMENDED_COUNT) {
    try {
      const params = new URLSearchParams({ page_size: String(FALLBACK_PAGE_SIZE) });
      const res = await fetch(`${API_BASE_URL}/products/?${params}`, { next: { revalidate: 60 } });
      if (!res.ok) throw new Error(`Products API responded ${res.status}`);
      const data = await res.json();
      (data.results ?? []).forEach(add);
    } catch (error) {
      console.error("Failed to load recommended products:", error);
    }
  }

  return picked.slice(0, RECOMMENDED_COUNT);
}

// Streaming placeholder for the section below while its recommendations resolve.
export function RecommendedProductsSkeleton() {
  return (
    <section aria-hidden="true" className="detail-section mt-16 border-t pt-10">
      <div className="product-skeleton__line h-8 w-56 animate-pulse rounded-full" />
      <div className="mt-6 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4 lg:gap-5">
        {Array.from({ length: RECOMMENDED_COUNT }, (_, i) => (
          <div key={i} className="product-card p-3 sm:p-4">
            <div className="product-skeleton__line aspect-square animate-pulse" style={{ borderRadius: "var(--radius-card)" }} />
            <div className="product-skeleton__line mt-4 h-4 w-3/4 animate-pulse rounded-full" />
            <div className="product-skeleton__line mt-2 h-4 w-1/3 animate-pulse rounded-full" />
          </div>
        ))}
      </div>
    </section>
  );
}

// Shown with the standard ProductCard so add-to-cart / select options / notify-me behave exactly as elsewhere.
// Renders nothing when there are no eligible products at all.
export default async function RecommendedProducts({ product, currencySymbol }) {
  const products = await getRecommendedProducts(product);
  if (!products.length) return null;
  return (
    <section aria-labelledby="recommended-heading" className="detail-section mt-16 border-t pt-10">
      <h2 id="recommended-heading" className="custom-font text-2xl sm:text-3xl">
        Recommended For You
      </h2>
      <div className="mt-6 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4 lg:gap-5">
        {products.map((item) => (
          <ProductCard key={item.id} product={item} currencySymbol={currencySymbol} />
        ))}
      </div>
    </section>
  );
}
