"use client";

import ProductCard from "@/component/shared/ProductCard";
import useScrollEdges from "@/lib/useScrollEdges";

const arrow = (dir) => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={dir === "left" ? "M19 12H5M11 6l-6 6 6 6" : "M5 12h14M13 6l6 6-6 6"} />
  </svg>
);

// Editorial header (title | description | arrows) above a CSS scroll-snap grid.
// `columns` is the desktop column count (tablet shows up to 3, mobile up to 2); `rows` stacks cards per page.
// The arrows page through the products one full view at a time.
export default function ProductCarousel({ products, currencySymbol, title, description, columns = 4, rows = 1 }) {
  const { ref, edges, update, scrollBy } = useScrollEdges();
  const showNav = !(edges.start && edges.end);

  return (
    <>
      <div className="mb-8 grid grid-cols-[minmax(0,1fr)_auto] items-end gap-x-6 gap-y-3 md:mb-10 lg:flex lg:justify-between lg:gap-x-12">
        <h2 className="custom-font max-w-[12em] text-3xl leading-[1.1] sm:text-4xl">{title}</h2>

        {/* Mobile: these two are placed straight into the grid (display: contents). Desktop: one right-hand group. */}
        <div className="contents lg:flex lg:min-w-0 lg:items-end lg:gap-10">
        {description && (
          <p className="showcase-muted col-span-2 row-start-2 max-w-md text-sm leading-relaxed lg:col-auto lg:row-auto lg:max-w-sm">
            {description}
          </p>
        )}

        {showNav && (
          <div className="col-start-2 row-start-1 flex shrink-0 items-center gap-2 sm:gap-3 lg:col-auto lg:row-auto">
            <button
              type="button"
              onClick={() => scrollBy(-1, { fraction: 1, page: true })}
              disabled={edges.start}
              aria-label="Previous products"
              className="pc-nav flex h-10 w-10 items-center justify-center rounded-full sm:h-12 sm:w-16"
            >
              {arrow("left")}
            </button>
            <button
              type="button"
              onClick={() => scrollBy(1, { fraction: 1, page: true })}
              disabled={edges.end}
              aria-label="Next products"
              className="pc-nav pc-nav--next flex h-10 w-10 items-center justify-center rounded-full sm:h-12 sm:w-16"
            >
              {arrow("right")}
            </button>
          </div>
        )}
        </div>
      </div>

      <ul
        ref={ref}
        onScroll={update}
        className="product-track"
        style={{ "--pc-cols": columns, "--pc-rows": rows }}
      >
        {products.map((product) => (
          <li key={product.id} className="product-track__item min-w-0">
            <ProductCard product={product} currencySymbol={currencySymbol} />
          </li>
        ))}
      </ul>
    </>
  );
}
