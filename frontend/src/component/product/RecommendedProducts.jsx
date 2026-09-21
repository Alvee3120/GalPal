import ProductCard from "@/component/shared/ProductCard";

// "Recommended For You": the backend's related products for this product (published items from the same primary
// category, excluding the product itself), shown with the standard ProductCard so add-to-cart / select options /
// notify-me behave exactly as elsewhere. Renders nothing when there are none.
export default function RecommendedProducts({ products, currencySymbol }) {
  if (!products?.length) return null;
  return (
    <section aria-labelledby="recommended-heading" className="detail-section mt-16 border-t pt-10">
      <h2 id="recommended-heading" className="custom-font text-2xl sm:text-3xl">
        Recommended For You
      </h2>
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4 lg:gap-5">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} currencySymbol={currencySymbol} />
        ))}
      </div>
    </section>
  );
}
