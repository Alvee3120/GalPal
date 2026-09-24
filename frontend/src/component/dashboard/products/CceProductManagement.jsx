"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiEdit2, FiPlus, FiSearch, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { PRODUCT_STATUS_LABEL, STOCK_STATUS_LABEL, catalogFetch, errorText } from "@/lib/productAdmin";
import ProductImage from "@/component/shared/ProductImage";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 10;
const SEARCH_DELAY_MS = 350;

// What the Stock column shows, from the backend's own stock fields: a variant product sells from its variants
// (apps.catalog.serializers_product.AdminProductListSerializer.variant_stock), so the parent's row is never shown
// as if it were the stock; untracked stock (manage_stock off) is always available rather than "0".
function stockText(p) {
  if (p.has_variants && p.variant_stock) {
    const v = p.variant_stock;
    const tracked = `${v.stock_quantity} across ${v.active_count} active variant${v.active_count === 1 ? "" : "s"}`;
    return v.untracked_count ? `${tracked} (+${v.untracked_count} untracked)` : tracked;
  }
  if (!p.manage_stock) return "Not tracked";
  if (p.stock_status === "backorder") return `${p.stock_quantity} (${STOCK_STATUS_LABEL.backorder})`;
  return String(p.stock_quantity);
}

// A discount that isn't currently applied (scheduled or expired sale) is flagged, so the column never implies a
// price customers aren't actually paying. effective_price is the backend's own "what it sells for now".
function DiscountCell({ product, currencySymbol }) {
  if (product.discount_price === null || product.discount_price === undefined) return <span className="showcase-muted">—</span>;
  const active = Number(product.effective_price) === Number(product.discount_price);
  return (
    <span>
      {formatPrice(product.discount_price, currencySymbol)}
      {!active && <span className="showcase-muted block text-xs">Not active now</span>}
    </span>
  );
}

function StatusBadge({ status }) {
  return (
    <span className="product-status-badge rounded-full px-2.5 py-1 text-xs font-medium" data-status={status}>
      {PRODUCT_STATUS_LABEL[status] ?? status}
    </span>
  );
}

function RowActions({ product, onDelete }) {
  return (
    <div className="flex items-center justify-end gap-1.5">
      <Link
        href={`/dashboard/CCE/products/${product.id}`}
        title="Edit product"
        aria-label={`Edit product ${product.name}`}
        className="icon-action flex h-9 w-9 items-center justify-center rounded-full"
      >
        <FiEdit2 className="h-4 w-4" aria-hidden="true" />
      </Link>
      <button
        type="button"
        onClick={() => onDelete(product)}
        title="Delete product"
        aria-label={`Delete product ${product.name}`}
        className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full"
      >
        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

// CCE Product Management: the EXISTING /admin/products/ API (apps.catalog.views_product_admin.AdminProductViewSet,
// IsCatalogStaff for list/retrieve/create/edit/delete). Search and pagination are server-side (`search` covers
// name, SKU, barcode and brand name); nothing is filtered in the browser.
export default function CceProductManagement({ initialProducts, initialCount, currencySymbol }) {
  const [products, setProducts] = useState(initialProducts);
  const [count, setCount] = useState(initialCount);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const requestId = useRef(0);
  const firstRender = useRef(true);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextSearch, nextPage) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    const res = await catalogFetch(`products?${params.toString()}`);
    if (id !== requestId.current) return; // a newer search/page superseded this one
    setLoading(false);
    if (!res.ok) {
      // A page past the end (e.g. after deleting the last row on it) falls back to the previous page.
      if (res.status === 404 && nextPage > 1) return load(nextSearch, nextPage - 1);
      notify.error(errorText(res, "Unable to load products. Please try again."));
      return;
    }
    setProducts(res.data.results ?? []);
    setCount(res.data.count ?? 0);
    setPage(nextPage);
  }

  // Debounced search; always back to page 1 so results start from the first match.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = setTimeout(() => load(search, 1), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  async function confirmDelete() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    const res = await catalogFetch(`products/${pendingDelete.id}`, { method: "DELETE" });
    setDeleting(false);
    if (!res.ok) {
      notify.error(errorText(res, "Unable to delete the product. Please try again."));
      return;
    }
    notify.success("Product deleted successfully.");
    setPendingDelete(null);
    load(search, page);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Product Management</h1>
          <p className="showcase-muted mt-1 text-sm">
            {count} product{count === 1 ? "" : "s"}
          </p>
        </div>
        <Link href="/dashboard/CCE/products/new" className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          Add Product
        </Link>
      </div>

      <div className="relative">
        <label htmlFor="pm-search" className="sr-only">
          Search products
        </label>
        <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
        <input
          id="pm-search"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search products by name or SKU..."
          className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
        />
      </div>

      {products.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">{loading ? "Loading..." : "No products found"}</p>
          {!loading && <p className="showcase-muted text-sm">{search.trim() ? "Try a different name or SKU." : "Add your first product to get started."}</p>}
        </div>
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          {/* Tablet/desktop: a real table (scrolls inside its own card if it ever outgrows the width). */}
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Image</th>
                  <th scope="col" className="px-4 py-3 font-medium">Name</th>
                  <th scope="col" className="px-4 py-3 font-medium">Status</th>
                  <th scope="col" className="px-4 py-3 font-medium">Regular Price</th>
                  <th scope="col" className="px-4 py-3 font-medium">Discount Price</th>
                  <th scope="col" className="px-4 py-3 font-medium">Stock</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.id}>
                    <td className="px-4 py-3">
                      <div className="cart-thumb relative h-12 w-12 overflow-hidden rounded-lg">
                        <ProductImage src={p.feature_image} alt="" tight />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium leading-snug">{p.name}</p>
                      <p className="showcase-muted text-xs">{p.sku}</p>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={p.status} />
                    </td>
                    <td className="px-4 py-3 tabular-nums">{formatPrice(p.regular_price, currencySymbol)}</td>
                    <td className="px-4 py-3 tabular-nums">
                      <DiscountCell product={p} currencySymbol={currencySymbol} />
                    </td>
                    <td className="px-4 py-3 tabular-nums">{stockText(p)}</td>
                    <td className="px-4 py-3">
                      <RowActions product={p} onDelete={setPendingDelete} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Phone: one card per product with the same fields. */}
          <ul className="flex flex-col gap-3 md:hidden">
            {products.map((p) => (
              <li key={p.id} className="dashboard-card flex gap-3 rounded-2xl p-4">
                <div className="cart-thumb relative h-16 w-16 shrink-0 overflow-hidden rounded-lg">
                  <ProductImage src={p.feature_image} alt="" tight />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium leading-snug">{p.name}</p>
                      <p className="showcase-muted text-xs">{p.sku}</p>
                    </div>
                    <StatusBadge status={p.status} />
                  </div>
                  <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                    <dt className="showcase-muted">Regular</dt>
                    <dd className="tabular-nums">{formatPrice(p.regular_price, currencySymbol)}</dd>
                    <dt className="showcase-muted">Discount</dt>
                    <dd className="tabular-nums">
                      <DiscountCell product={p} currencySymbol={currencySymbol} />
                    </dd>
                    <dt className="showcase-muted">Stock</dt>
                    <dd className="tabular-nums">{stockText(p)}</dd>
                  </dl>
                  <div className="mt-2">
                    <RowActions product={p} onDelete={setPendingDelete} />
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(next) => next !== page && load(search, next)} disabled={loading} />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Product?"
        description={pendingDelete ? `Are you sure you want to delete "${pendingDelete.name}"?` : ""}
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}
