import Link from "next/link";

// Breadcrumb + page title band, shared by /shop, /cart and any future top-level page. Matches the muted
// section other pages (e.g. the category showcase) already use.
export default function PageHero({ title }) {
  return (
    <div className="shop-hero w-full py-10 text-center sm:py-14 mb-5">
      <h1 className="custom-font text-3xl sm:text-4xl">{title}</h1>
      <nav aria-label="Breadcrumb" className="showcase-muted mt-2 text-sm">
        <Link href="/" className="hover:underline">
          Home
        </Link>
        <span className="mx-2" aria-hidden="true">
          /
        </span>
        <span aria-current="page">{title}</span>
      </nav>
    </div>
  );
}
