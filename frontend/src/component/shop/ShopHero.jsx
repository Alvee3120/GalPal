import Link from "next/link";

// Breadcrumb + page title band, matching the muted section other pages (e.g. the category showcase) already use.
export default function ShopHero() {
  return (
    <div className="shop-hero w-full py-10 text-center sm:py-14 mb-5">
      <h1 className="custom-font text-3xl sm:text-4xl">Shop</h1>
      <nav aria-label="Breadcrumb" className="showcase-muted mt-2 text-sm">
        <Link href="/" className="hover:underline">
          Home
        </Link>
        <span className="mx-2" aria-hidden="true">
          /
        </span>
        <span aria-current="page">Shop</span>
      </nav>
    </div>
  );
}
