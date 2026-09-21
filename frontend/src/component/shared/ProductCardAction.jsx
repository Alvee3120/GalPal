"use client";

import Link from "next/link";
import AddToCartButton from "./AddToCartButton";
import NotifyMeButton from "./NotifyMeButton";
import { getStockAction } from "@/lib/productStock";

// The product card's action area: which of Add to Cart / Select Options / Notify Me shows is
// decided ONLY by the real API fields (in_stock, has_variants) via getStockAction — never by
// product name/id or a frontend guess. See lib/productStock.js.
export default function ProductCardAction({ product, compact = false }) {
  const action = getStockAction(product);

  if (action === "add") {
    return <AddToCartButton product={product} compact={compact} />;
  }

  if (action === "select") {
    const label = "Select Options";
    if (compact) {
      return (
        <Link
          href={`/products/${product.slug}`}
          aria-label={`${label} for ${product.name}`}
          className="auth-btn auth-btn--primary flex h-10 shrink-0 items-center justify-center rounded-full px-3 text-xs font-medium"
        >
          {label}
        </Link>
      );
    }
    return (
      <div className="mt-3 sm:mt-4">
        <Link
          href={`/products/${product.slug}`}
          className="auth-btn auth-btn--primary block w-full rounded-full px-4 py-2.5 text-center text-sm font-medium"
        >
          {label}
        </Link>
      </div>
    );
  }

  // action === "notify"
  return (
    <div className={compact ? "shrink-0" : "mt-3 sm:mt-4"}>
      <NotifyMeButton
        productId={product.id}
        productName={product.name}
        compact={compact}
        ariaLabel={`Notify me when ${product.name} is back in stock`}
        className={
          compact
            ? "auth-btn product-card__action--notify flex h-10 w-10 items-center justify-center rounded-full text-xs font-medium"
            : "auth-btn product-card__action--notify w-full rounded-full px-4 py-2.5 text-sm font-medium"
        }
      />
    </div>
  );
}
