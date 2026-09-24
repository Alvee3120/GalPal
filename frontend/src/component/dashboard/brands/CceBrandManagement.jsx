"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiEdit2, FiPlus, FiSearch, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { catalogFetch, errorText } from "@/lib/productAdmin";
import ProductImage from "@/component/shared/ProductImage";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 10;
const SEARCH_DELAY_MS = 350;

function ActiveBadge({ active }) {
  return (
    <span className="product-status-badge rounded-full px-2.5 py-1 text-xs font-medium" data-status={active ? "active" : "inactive"}>
      {active ? "Active" : "Inactive"}
    </span>
  );
}

function RowActions({ brand, onDelete }) {
  return (
    <div className="flex items-center justify-end gap-1.5">
      <Link
        href={`/dashboard/CCE/brands/${brand.id}`}
        title="Edit brand"
        aria-label={`Edit brand ${brand.name}`}
        className="icon-action flex h-9 w-9 items-center justify-center rounded-full"
      >
        <FiEdit2 className="h-4 w-4" aria-hidden="true" />
      </Link>
      <button
        type="button"
        onClick={() => onDelete(brand)}
        title="Delete brand"
        aria-label={`Delete brand ${brand.name}`}
        className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full"
      >
        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

// A logo, whole and uncropped (ProductImage's `tight` mode is object-contain), with the site's faint-logo fallback.
function Logo({ src }) {
  return (
    <div className="cart-thumb relative h-12 w-16 shrink-0 overflow-hidden rounded-lg">
      <ProductImage src={src} alt="" tight />
    </div>
  );
}

// CCE Brand Management over the EXISTING /admin/brands/ API (apps.catalog.views_admin.AdminBrandViewSet — the same
// endpoints and serializer Admin uses; CCE is let in per action by IsCatalogStaff). Search (name/slug) and
// pagination are server-side.
export default function CceBrandManagement({ initialBrands, initialCount }) {
  const [brands, setBrands] = useState(initialBrands);
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
    const res = await catalogFetch(`brands?${params.toString()}`);
    if (id !== requestId.current) return; // superseded by a newer search/page
    setLoading(false);
    if (!res.ok) {
      if (res.status === 404 && nextPage > 1) return load(nextSearch, nextPage - 1); // page emptied by a delete
      notify.error(errorText(res, "Unable to load brands. Please try again."));
      return;
    }
    setBrands(res.data.results ?? []);
    setCount(res.data.count ?? 0);
    setPage(nextPage);
  }

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
    const res = await catalogFetch(`brands/${pendingDelete.id}`, { method: "DELETE" });
    setDeleting(false);
    if (!res.ok) {
      notify.error(errorText(res, "Unable to delete the brand. Please try again."));
      setPendingDelete(null);
      return;
    }
    notify.success("Brand deleted successfully.");
    setPendingDelete(null);
    load(search, page);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Brand Management</h1>
          <p className="showcase-muted mt-1 text-sm">
            {count} brand{count === 1 ? "" : "s"}
          </p>
        </div>
        <Link href="/dashboard/CCE/brands/new" className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          Add Brand
        </Link>
      </div>

      <div className="relative">
        <label htmlFor="bm-search" className="sr-only">
          Search brands
        </label>
        <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
        <input
          id="bm-search"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search brands..."
          className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
        />
      </div>

      {brands.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">{loading ? "Loading..." : "No brands found"}</p>
          {!loading && <p className="showcase-muted text-sm">{search.trim() ? "Try a different name." : "Add your first brand to get started."}</p>}
        </div>
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[480px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Logo</th>
                  <th scope="col" className="px-4 py-3 font-medium">Name</th>
                  <th scope="col" className="px-4 py-3 font-medium">Is Active</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {brands.map((b) => (
                  <tr key={b.id}>
                    <td className="px-4 py-3">
                      <Logo src={b.logo} />
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium leading-snug">{b.name}</p>
                      <p className="showcase-muted text-xs">{b.slug}</p>
                    </td>
                    <td className="px-4 py-3">
                      <ActiveBadge active={b.is_active} />
                    </td>
                    <td className="px-4 py-3">
                      <RowActions brand={b} onDelete={setPendingDelete} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 md:hidden">
            {brands.map((b) => (
              <li key={b.id} className="dashboard-card flex items-center gap-3 rounded-2xl p-4">
                <Logo src={b.logo} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium leading-snug">{b.name}</p>
                  <div className="mt-1.5">
                    <ActiveBadge active={b.is_active} />
                  </div>
                </div>
                <RowActions brand={b} onDelete={setPendingDelete} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(next) => next !== page && load(search, next)} disabled={loading} />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Brand?"
        description={
          pendingDelete
            ? `Are you sure you want to delete "${pendingDelete.name}"? Products with this brand will be kept, just without a brand.`
            : ""
        }
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}
