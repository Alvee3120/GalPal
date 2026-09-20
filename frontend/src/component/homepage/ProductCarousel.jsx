"use client";

import ProductCard from "@/component/shared/ProductCard";
import SectionHeader from "@/component/shared/SectionHeader";
import CarouselArrows from "@/component/shared/CarouselArrows";
import useScrollEdges from "@/lib/useScrollEdges";

// Editorial header (title | description | arrows) above a CSS scroll-snap grid.
// `columns` is the desktop column count (tablet shows up to 3, mobile up to 2); `rows` stacks cards per page.
// The arrows page through the products one full view at a time.
export default function ProductCarousel({ products, currencySymbol, title, description, columns = 4, rows = 1 }) {
  const { ref, edges, update, scrollBy } = useScrollEdges();
  const showNav = !(edges.start && edges.end);

  return (
    <>
      <SectionHeader
        title={title}
        description={description}
        actions={
          showNav && (
            <CarouselArrows
              onPrev={() => scrollBy(-1, { fraction: 1, page: true })}
              onNext={() => scrollBy(1, { fraction: 1, page: true })}
              prevDisabled={edges.start}
              nextDisabled={edges.end}
              prevLabel="Previous products"
              nextLabel="Next products"
            />
          )
        }
      />

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
