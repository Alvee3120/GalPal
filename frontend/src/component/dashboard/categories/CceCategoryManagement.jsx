"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiEdit2, FiPlus, FiSearch, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { catalogFetch, errorText } from "@/lib/productAdmin";
import { flattenCategoryTree } from "@/lib/categoryAdmin";
import ProductImage from "@/component/shared/ProductImage";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import DashboardPagination from "../DashboardPagination";
import { useStaffHref } from "@/lib/staffPaths";

const PAGE_SIZE = 10;
const SEARCH_DELAY_MS = 350;

function ActiveBadge({ active }) {
  return (
    <span className="product-status-badge rounded-full px-2.5 py-1 text-xs font-medium" data-status={active ? "active" : "inactive"}>
      {active ? "Active" : "Inactive"}
    </span>
  );
}

function RowActions({ category, onDelete }) {
  const to = useStaffHref();
  return (
    <div className="flex items-center justify-end gap-1.5">
      <Link
        href={to(`/dashboard/CCE/categories/${category.id}`)}
        title="Edit category"
        aria-label={`Edit category ${category.name}`}
        className="icon-action flex h-9 w-9 items-center justify-center rounded-full"
      >
        <FiEdit2 className="h-4 w-4" aria-hidden="true" />
      </Link>
      <button
        type="button"
        onClick={() => onDelete(category)}
        title="Delete category"
        aria-label={`Delete category ${category.name}`}
        className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full"
      >
        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

// CCE Category Management over the EXISTING /admin/categories/ API (apps.catalog.views_admin.AdminCategoryViewSet —
// the same endpoints, serializer and services Admin uses; CCE is let in per action by IsCatalogStaff). Search
// (name/slug) and pagination are server-side. The list returns `parent` as an id, so parent names come from the
// category tree (/admin/categories/tree/, every category in one small response) rather than guessing from the page.
export default function CceCategoryManagement({ initialCategories, initialCount, initialTree }) {
  const to = useStaffHref();
  const [categories, setCategories] = useState(initialCategories);
  const [count, setCount] = useState(initialCount);
  const [names, setNames] = useState(() => new Map(flattenCategoryTree(initialTree).map((c) => [c.id, c.name])));
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState(""); // "" | "active" | "inactive"
  const [level, setLevel] = useState(""); // "" | "top" | "sub"
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const requestId = useRef(0);
  const firstRender = useRef(true);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextSearch, nextPage, nextStatus = status, nextLevel = level) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    // The backend's own filters (apps.catalog.filters.AdminCategoryFilter): is_active and top_level.
    if (nextStatus) params.set("is_active", nextStatus === "active" ? "true" : "false");
    if (nextLevel) params.set("top_level", nextLevel === "top" ? "true" : "false");
    const [res, tree] = await Promise.all([catalogFetch(`categories?${params.toString()}`), catalogFetch("categories/tree")]);
    if (id !== requestId.current) return; // superseded by a newer search/page
    setLoading(false);
    if (tree.ok) setNames(new Map(flattenCategoryTree(tree.data).map((c) => [c.id, c.name])));
    if (!res.ok) {
      if (res.status === 404 && nextPage > 1) return load(nextSearch, nextPage - 1, nextStatus, nextLevel); // page emptied by a delete
      notify.error(errorText(res, "Unable to load categories. Please try again."));
      return;
    }
    setCategories(res.data.results ?? []);
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
    const res = await catalogFetch(`categories/${pendingDelete.id}`, { method: "DELETE" });
    setDeleting(false);
    if (!res.ok) {
      // e.g. 409 "This category has 3 product(s)…" / "…has 2 sub-categories…" — shown as the backend words it.
      notify.error(errorText(res, "Unable to delete the category. Please try again."));
      setPendingDelete(null);
      return;
    }
    notify.success("Category deleted successfully.");
    setPendingDelete(null);
    load(search, page);
  }

  const parentName = (c) => (c.parent === null || c.parent === undefined ? "—" : (names.get(c.parent) ?? "—"));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Category Management</h1>
          <p className="showcase-muted mt-1 text-sm">
            {count} categor{count === 1 ? "y" : "ies"}
          </p>
        </div>
        <Link href={to("/dashboard/CCE/categories/new")} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          Add Category
        </Link>
      </div>

      {/* A grid, not flex: .checkout-input is width:100%, so the grid (not a w-* class) sizes each control. */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,10rem)_minmax(0,11rem)]">
        <div className="relative col-span-2 min-w-0 sm:col-span-1">
          <label htmlFor="cm-search" className="sr-only">
            Search categories
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            id="cm-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search categories..."
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
        <label htmlFor="cm-status" className="sr-only">
          Filter by status
        </label>
        <select
          id="cm-status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            load(search, 1, e.target.value, level);
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
        </select>
        <label htmlFor="cm-level" className="sr-only">
          Filter by level
        </label>
        <select
          id="cm-level"
          value={level}
          onChange={(e) => {
            setLevel(e.target.value);
            load(search, 1, status, e.target.value);
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All categories</option>
          <option value="top">Top-level only</option>
          <option value="sub">Sub-categories only</option>
        </select>
      </div>

      {categories.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">{loading ? "Loading..." : "No categories found"}</p>
          {!loading && <p className="showcase-muted text-sm">{search.trim() || status || level ? "Try a different search or filter." : "Add your first category to get started."}</p>}
        </div>
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[560px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Image</th>
                  <th scope="col" className="px-4 py-3 font-medium">Name</th>
                  <th scope="col" className="px-4 py-3 font-medium">Parent</th>
                  <th scope="col" className="px-4 py-3 font-medium">Is Active</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {categories.map((c) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3">
                      <div className="cart-thumb relative h-12 w-12 overflow-hidden rounded-lg">
                        <ProductImage src={c.image} alt="" tight />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium leading-snug">{c.name}</p>
                      <p className="showcase-muted text-xs">{c.slug}</p>
                    </td>
                    <td className="px-4 py-3">{parentName(c)}</td>
                    <td className="px-4 py-3">
                      <ActiveBadge active={c.is_active} />
                    </td>
                    <td className="px-4 py-3">
                      <RowActions category={c} onDelete={setPendingDelete} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 md:hidden">
            {categories.map((c) => (
              <li key={c.id} className="dashboard-card flex gap-3 rounded-2xl p-4">
                <div className="cart-thumb relative h-14 w-14 shrink-0 overflow-hidden rounded-lg">
                  <ProductImage src={c.image} alt="" tight />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium leading-snug">{c.name}</p>
                      <p className="showcase-muted text-xs">Parent: {parentName(c)}</p>
                    </div>
                    <ActiveBadge active={c.is_active} />
                  </div>
                  <div className="mt-2">
                    <RowActions category={c} onDelete={setPendingDelete} />
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
        title="Delete Category?"
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
