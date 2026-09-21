import ProductCard from "@/component/shared/ProductCard";

export function ShopProductGridSkeleton({ count = 12 }) {
  return (
    <div className="shop-grid grid grid-cols-2 gap-4 sm:gap-5 md:grid-cols-3">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="product-card p-3 sm:p-4">
          <div className="product-skeleton__line aspect-square animate-pulse" style={{ borderRadius: "var(--radius-card)" }} />
          <div className="product-skeleton__line mt-4 h-4 w-3/4 animate-pulse rounded-full" />
          <div className="product-skeleton__line mt-2 h-4 w-1/3 animate-pulse rounded-full" />
        </div>
      ))}
    </div>
  );
}

export default function ShopProductGrid({ products, currencySymbol }) {
  if (products.length === 0) {
    return (
      <div className="shop-empty rounded-2xl px-6 py-16 text-center">
        <p className="custom-font text-2xl">No products found</p>
        <p className="showcase-muted mt-2 text-sm">Try adjusting or clearing your filters.</p>
      </div>
    );
  }

  return (
    <div className="shop-grid grid grid-cols-2 gap-4 sm:gap-5 md:grid-cols-3">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} currencySymbol={currencySymbol} showRating />
      ))}
    </div>
  );
}
