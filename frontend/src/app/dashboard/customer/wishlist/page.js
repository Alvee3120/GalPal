import Link from "next/link";
import { FiHeart } from "react-icons/fi";
import { backendFetch } from "@/lib/backendAuth";
import { getCurrencySymbol } from "@/lib/siteSettings";
import ProductCard from "@/component/shared/ProductCard";

export const metadata = { title: "My Wishlist | GalPal" };

// The customer's saved products (GET /wishlist/, their own only). Each card has the same heart to remove it and the
// usual Add to Cart button. Products that were unpublished since are hidden, not deleted.
async function getWishlist() {
  try {
    const res = await backendFetch("/wishlist/");
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

export default async function WishlistPage() {
  const [wishlist, currencySymbol] = await Promise.all([getWishlist(), getCurrencySymbol()]);
  const products = wishlist?.products ?? [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">My Wishlist</h1>
        <p className="showcase-muted mt-1 text-sm">
          {products.length} saved product{products.length === 1 ? "" : "s"}
        </p>
      </div>

      {!wishlist ? (
        <div className="dashboard-card rounded-2xl px-6 py-14 text-center text-sm">Unable to load your wishlist. Please refresh the page.</div>
      ) : products.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <FiHeart className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">Your wishlist is empty</p>
          <p className="showcase-muted text-sm">Tap the heart on any product to save it for later.</p>
          <Link href="/shop" className="auth-btn auth-btn--primary mt-2 rounded-full px-6 py-2.5 text-sm font-medium">
            Browse the Shop
          </Link>
        </div>
      ) : (
        <ul className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-4">
          {products.map((product) => (
            <li key={product.id}>
              <ProductCard product={product} currencySymbol={currencySymbol} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
