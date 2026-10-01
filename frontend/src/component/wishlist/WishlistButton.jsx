"use client";

import { FiHeart } from "react-icons/fi";
import { useWishlist } from "./WishlistProvider";

// The heart toggle on product cards and the product page. Filled when the product is in the customer's wishlist.
export default function WishlistButton({ productId, productName, className = "", size = "md" }) {
  const wishlist = useWishlist();
  if (!wishlist) return null;
  const saved = wishlist.ids.has(productId);
  const dimensions = size === "lg" ? "h-12 w-12" : "h-9 w-9";
  return (
    <button
      type="button"
      onClick={() => wishlist.toggle(productId, productName)}
      disabled={wishlist.isPending(productId)}
      aria-pressed={saved}
      aria-label={saved ? `Remove ${productName ?? "product"} from wishlist` : `Save ${productName ?? "product"} to wishlist`}
      title={saved ? "Remove from wishlist" : "Save to wishlist"}
      className={`wishlist-btn flex ${dimensions} shrink-0 items-center justify-center rounded-full ${className}`}
      data-saved={saved || undefined}
    >
      <FiHeart className={size === "lg" ? "h-5 w-5" : "h-4 w-4"} aria-hidden="true" />
    </button>
  );
}
