import Link from "next/link";
import formatPrice from "@/lib/formatPrice";
import ProductImage from "./ProductImage";
import AddToCartButton from "./AddToCartButton";
import StarRating from "./StarRating";

// Reusable product tile. `product` is an item from the backend's /products/ list.
// The link covers the photo and text; the Add to Cart button sits outside it (a button must not live inside a link).
//   variant="compact"  a slim horizontal card (thumbnail | name + price | Add), used under shoppable videos.
//                      Same data, same link, same image handling, same cart button as the default tile.
//   showRating         adds the star rating under the name (opt-in: only the Shop grid asks for it, so the
//                      homepage carousels keep their current, rating-free look).
export default function ProductCard({ product, currencySymbol = "", variant = "default", className = "", showRating = false }) {
  const { name, slug, feature_image: image, effective_price, regular_price, on_sale, discount_percentage, in_stock, brand, primary_category, average_rating, review_count } = product;
  const info = brand?.name ?? primary_category?.name;
  const discounted = on_sale && regular_price !== effective_price;

  if (variant === "compact") {
    return (
      <article className={`product-card product-card--compact group flex items-center gap-3 p-2.5 ${className}`}>
        <Link href={`/products/${slug}`} className="product-card__link flex min-w-0 flex-1 items-center gap-3 rounded-[inherit]">
          <div className="product-card__media relative h-14 w-14 shrink-0 overflow-hidden sm:h-16 sm:w-16">
            <ProductImage src={image} alt={name} tight />
          </div>
          <div className="min-w-0">
            <h3 className="product-card__name line-clamp-2 text-sm font-medium leading-snug">{name}</h3>
            <p className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5 text-sm">
              <span className="product-card__price font-semibold">{formatPrice(effective_price, currencySymbol)}</span>
              {discounted && <span className="showcase-muted text-xs line-through">{formatPrice(regular_price, currencySymbol)}</span>}
              {discounted && discount_percentage > 0 && <span className="product-card__chip rounded-full px-1.5 py-0.5 text-[0.625rem] font-medium">-{discount_percentage}%</span>}
            </p>
          </div>
        </Link>
        <AddToCartButton product={product} compact />
      </article>
    );
  }

  return (
    <article className="product-card group flex h-full flex-col p-3 sm:p-4">
      <Link href={`/products/${slug}`} className="product-card__link block rounded-[inherit]">
        <div className="product-card__media relative aspect-square overflow-hidden">
          <ProductImage src={image} alt={name} />
          {on_sale && discount_percentage > 0 && (
            <span className="product-card__badge absolute left-2 top-2 rounded-full px-3 py-1 text-xs font-medium sm:left-3 sm:top-3">
              {discount_percentage}% OFF
            </span>
          )}
          {in_stock === false && (
            <span className="product-card__badge absolute bottom-2 left-2 rounded-full px-3 py-1 text-xs font-medium sm:bottom-3 sm:left-3">
              Out of stock
            </span>
          )}
        </div>

        <div className="mt-3 flex flex-col gap-1 sm:mt-4 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
          <div className="min-w-0">
            <h3 className="product-card__name line-clamp-2 text-sm font-medium leading-snug sm:text-base">{name}</h3>
            {info && <p className="showcase-muted mt-0.5 truncate text-xs">{info}</p>}
            {showRating && <StarRating rating={average_rating} count={Number(review_count) || 0} className="mt-1" />}
          </div>
          <p className="shrink-0 text-sm sm:text-right sm:text-base">
            <span className="font-semibold">{formatPrice(effective_price, currencySymbol)}</span>
            {discounted && (
              <span className="showcase-muted ml-2 text-xs line-through sm:ml-0 sm:block">
                {formatPrice(regular_price, currencySymbol)}
              </span>
            )}
          </p>
        </div>
      </Link>

      <div className="mt-auto">
        <AddToCartButton product={product} />
      </div>
    </article>
  );
}
