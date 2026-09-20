"use client";

import Image from "next/image";
import Link from "next/link";
import useScrollEdges from "@/lib/useScrollEdges";

const chevron = (dir) => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={dir === "left" ? "m15 6-6 6 6 6" : "m9 6 6 6-6 6"} />
  </svg>
);

// Route the cards link to; the category slug is the backend's public identifier.
const categoryHref = (category) => `/shop?category=${encodeURIComponent(category.slug)}`;

function CategoryCard({ category, priority }) {
  const hasImage = Boolean(category.image);
  return (
    <li className="w-[78%] shrink-0 snap-start sm:w-[46%] lg:w-[31%] xl:w-[23.5%]">
      <Link
        href={categoryHref(category)}
        aria-label={`Shop ${category.name}`}
        className={`category-card group relative block aspect-[3/4] overflow-hidden ${hasImage ? "" : "category-card--empty"}`}
      >
        {hasImage && (
          <Image
            src={category.image}
            alt=""
            fill
            unoptimized // backend media may live on a private host the Next optimizer cannot reach
            priority={priority}
            sizes="(min-width: 1280px) 24vw, (min-width: 1024px) 31vw, (min-width: 640px) 46vw, 78vw"
            className="category-card__img object-cover"
          />
        )}
        <span className="category-card__overlay absolute inset-0" aria-hidden="true" />
        <span className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 p-5 md:p-6">
          <span className="custom-font text-2xl leading-tight md:text-3xl">{category.name}</span>
          <span className="category-card__arrow flex h-10 w-10 shrink-0 items-center justify-center rounded-full" aria-hidden="true">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </span>
        </span>
      </Link>
    </li>
  );
}

// Header (heading left, prev/next buttons right, one flex row) above a horizontal scroll-snap row.
export default function CategoryRow({ categories, heading }) {
  const { ref: listRef, edges, update, scrollBy } = useScrollEdges();

  const showNav = !(edges.start && edges.end);

  return (
    <>
      <div className="mb-6 flex items-end justify-between gap-4 md:mb-8">
        <div className="min-w-0">{heading}</div>
        {showNav && (
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            {[-1, 1].map((dir) => (
              <button
                key={dir}
                type="button"
                onClick={() => scrollBy(dir)}
                disabled={dir < 0 ? edges.start : edges.end}
                aria-label={dir < 0 ? "Previous categories" : "Next categories"}
                className="showcase-nav flex h-9 w-9 items-center justify-center rounded-full sm:h-10 sm:w-10"
              >
                {chevron(dir < 0 ? "left" : "right")}
              </button>
            ))}
          </div>
        )}
      </div>
      <ul
        ref={listRef}
        onScroll={update}
        className="flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth pb-1 [scrollbar-width:none] md:gap-5 [&::-webkit-scrollbar]:hidden"
      >
        {categories.map((category, i) => (
          <CategoryCard key={category.id} category={category} priority={i < 3} />
        ))}
      </ul>
    </>
  );
}
