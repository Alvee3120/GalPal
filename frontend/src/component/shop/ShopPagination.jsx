import Link from "next/link";
import { buildShopHref } from "@/lib/shopQuery";

// Plain page links, no client JS. Shows a windowed run of pages around the current one plus first/last,
// with "…" gaps — the same shape as the reference ("< 1 2 3 … 10 >").
function pageList(current, total) {
  const pages = new Set([1, total, current, current - 1, current + 1]);
  return [...pages]
    .filter((p) => p >= 1 && p <= total)
    .sort((a, b) => a - b)
    .reduce((acc, p) => {
      if (acc.length && p - acc[acc.length - 1] > 1) acc.push("…");
      acc.push(p);
      return acc;
    }, []);
}

export default function ShopPagination({ page, totalPages, searchParams }) {
  if (totalPages <= 1) return null;

  return (
    <nav aria-label="Shop pagination" className="mt-10 flex items-center justify-center gap-1.5">
      <Link
        href={buildShopHref(searchParams, { page: Math.max(1, page - 1) })}
        aria-label="Previous page"
        aria-disabled={page === 1}
        className={`shop-page-btn flex h-9 w-9 items-center justify-center rounded-full text-sm ${page === 1 ? "pointer-events-none opacity-40" : ""}`}
      >
        ‹
      </Link>
      {pageList(page, totalPages).map((p, i) =>
        p === "…" ? (
          <span key={`gap-${i}`} className="shop-page-gap px-1 text-sm">
            …
          </span>
        ) : (
          <Link
            key={p}
            href={buildShopHref(searchParams, { page: p === 1 ? null : p })}
            aria-current={p === page ? "page" : undefined}
            className="shop-page-btn flex h-9 w-9 items-center justify-center rounded-full text-sm"
          >
            {p}
          </Link>
        ),
      )}
      <Link
        href={buildShopHref(searchParams, { page: Math.min(totalPages, page + 1) })}
        aria-label="Next page"
        aria-disabled={page === totalPages}
        className={`shop-page-btn flex h-9 w-9 items-center justify-center rounded-full text-sm ${page === totalPages ? "pointer-events-none opacity-40" : ""}`}
      >
        ›
      </Link>
    </nav>
  );
}
