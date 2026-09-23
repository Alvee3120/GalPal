"use client";

// Client-driven pagination (buttons + a page-change callback, not links) for dashboard lists that fetch their
// own page of results — Order Management and My Orders. Same windowed "1 2 … 10" shape and the same
// .shop-page-btn/.shop-page-gap styling as the storefront's ShopPagination, just callback-based instead of
// Link-based since these lists are client components managing their own fetch, not URL query params.
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

export default function DashboardPagination({ page, totalPages, onPageChange, disabled = false }) {
  if (totalPages <= 1) return null;

  return (
    <nav aria-label="Pagination" className="mt-2 flex items-center justify-center gap-1.5">
      <button
        type="button"
        onClick={() => onPageChange(Math.max(1, page - 1))}
        disabled={disabled || page === 1}
        aria-label="Previous page"
        className="shop-page-btn flex h-9 w-9 items-center justify-center rounded-full text-sm disabled:pointer-events-none disabled:opacity-40"
      >
        ‹
      </button>
      {pageList(page, totalPages).map((p, i) =>
        p === "…" ? (
          <span key={`gap-${i}`} className="shop-page-gap px-1 text-sm">
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            onClick={() => onPageChange(p)}
            disabled={disabled}
            aria-current={p === page ? "page" : undefined}
            className="shop-page-btn flex h-9 w-9 items-center justify-center rounded-full text-sm disabled:pointer-events-none"
          >
            {p}
          </button>
        ),
      )}
      <button
        type="button"
        onClick={() => onPageChange(Math.min(totalPages, page + 1))}
        disabled={disabled || page === totalPages}
        aria-label="Next page"
        className="shop-page-btn flex h-9 w-9 items-center justify-center rounded-full text-sm disabled:pointer-events-none disabled:opacity-40"
      >
        ›
      </button>
    </nav>
  );
}
