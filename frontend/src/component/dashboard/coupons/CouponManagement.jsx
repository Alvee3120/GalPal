"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiEdit2, FiPlus, FiSearch, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { errorText } from "@/lib/productAdmin";
import { formatOrderDateTime } from "@/lib/orderStatus";
import { COUPON_STATUSES, COUPON_STATUS_LABEL, COUPON_TYPES, COUPON_TYPE_LABEL, couponFetch } from "@/lib/couponAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 10;
const SEARCH_DELAY_MS = 350;

const amountText = (c, symbol) => (c.type === "percentage" ? `${Number(c.amount)}%` : formatPrice(c.amount, symbol));
const usageText = (c) => `${c.usage_count} / ${c.total_usage_limit ?? "Unlimited"}`;
const when = (iso, empty) => (iso ? formatOrderDateTime(iso) : <span className="showcase-muted">{empty}</span>);

function StatusBadge({ status }) {
  return (
    <span className="coupon-status rounded-full px-2.5 py-1 text-xs font-medium" data-status={status}>
      {COUPON_STATUS_LABEL[status] ?? status}
    </span>
  );
}

function Actions({ coupon, onDelete }) {
  return (
    <div className="flex items-center gap-1.5">
      <Link
        href={`/dashboard/admin/coupons/${coupon.id}`}
        title="Edit coupon"
        aria-label={`Edit coupon ${coupon.code}`}
        className="icon-action flex h-9 w-9 items-center justify-center rounded-full"
      >
        <FiEdit2 className="h-4 w-4" aria-hidden="true" />
      </Link>
      <button
        type="button"
        onClick={() => onDelete(coupon)}
        title="Delete coupon"
        aria-label={`Delete coupon ${coupon.code}`}
        className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full"
      >
        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

// Admin Coupons over the EXISTING /admin/coupons/ API (apps.coupons — IsAdmin). Search (code, description), the status
// filter (the backend's own active / scheduled / expired / used up / inactive, from dates, usage and is_active) and the
// type filter all run on the server with pagination. A used coupon can't be deleted (the backend keeps its usage history
// for past orders) — its message says to deactivate it instead.
export default function CouponManagement({ initialCoupons, initialCount, currencySymbol }) {
  const [coupons, setCoupons] = useState(initialCoupons);
  const [count, setCount] = useState(initialCount);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const requestId = useRef(0);
  const firstRender = useRef(true);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const filtered = Boolean(search.trim() || status || type);

  async function load({ nextSearch = search, nextStatus = status, nextType = type, nextPage = 1 } = {}) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    if (nextStatus) params.set("status", nextStatus);
    if (nextType) params.set("type", nextType);
    const res = await couponFetch(`?${params.toString()}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) {
      if (res.status === 404 && nextPage > 1) return load({ nextSearch, nextStatus, nextType, nextPage: nextPage - 1 });
      notify.error(errorText(res, "Unable to load coupons. Please try again."));
      return;
    }
    setCoupons(res.data.results ?? []);
    setCount(res.data.count ?? 0);
    setPage(nextPage);
  }

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = setTimeout(() => load({ nextSearch: search }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  function clearFilters() {
    setSearch("");
    setStatus("");
    setType("");
    load({ nextSearch: "", nextStatus: "", nextType: "" });
  }

  async function confirmDelete() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    const res = await couponFetch(`/${pendingDelete.id}`, { method: "DELETE" });
    setDeleting(false);
    setPendingDelete(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the coupon. Please try again."));
    notify.success("Coupon deleted successfully.");
    load({ nextPage: page });
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Coupons</h1>
          <p className="showcase-muted mt-1 text-sm">
            {count} coupon{count === 1 ? "" : "s"}
          </p>
        </div>
        <Link href="/dashboard/admin/coupons/new" className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          Add Coupon
        </Link>
      </div>

      {/* A grid, not flex: .checkout-input is width:100%, so the grid (not a w-* class) sizes each control. */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,10rem)_minmax(0,10rem)]">
        <div className="relative col-span-2 min-w-0 sm:col-span-1">
          <label htmlFor="cp-search" className="sr-only">
            Search coupons
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            id="cp-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search coupons..."
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
        <label htmlFor="cp-status" className="sr-only">
          Filter by status
        </label>
        <select
          id="cp-status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            load({ nextStatus: e.target.value });
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All statuses</option>
          {COUPON_STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <label htmlFor="cp-type" className="sr-only">
          Filter by type
        </label>
        <select
          id="cp-type"
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            load({ nextType: e.target.value });
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All types</option>
          {COUPON_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {coupons.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">{loading ? "Loading..." : "No coupons found."}</p>
          {!loading && filtered && (
            <button type="button" onClick={clearFilters} className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[900px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Code</th>
                  <th scope="col" className="px-4 py-3 font-medium">Type</th>
                  <th scope="col" className="px-4 py-3 font-medium">Amount</th>
                  <th scope="col" className="px-4 py-3 font-medium">Start At</th>
                  <th scope="col" className="px-4 py-3 font-medium">Expiry At</th>
                  <th scope="col" className="px-4 py-3 font-medium">Status</th>
                  <th scope="col" className="px-4 py-3 font-medium">Usage</th>
                  <th scope="col" className="px-4 py-3 font-medium">Edit</th>
                  <th scope="col" className="px-4 py-3 font-medium">Delete</th>
                </tr>
              </thead>
              <tbody>
                {coupons.map((c) => (
                  <tr key={c.id}>
                    <td className="px-4 py-3">
                      <p className="font-mono font-semibold">{c.code}</p>
                      {c.description && <p className="showcase-muted max-w-[14rem] truncate text-xs">{c.description}</p>}
                    </td>
                    <td className="px-4 py-3">{COUPON_TYPE_LABEL[c.type] ?? c.type}</td>
                    <td className="px-4 py-3 tabular-nums">
                      {amountText(c, currencySymbol)}
                      {c.free_shipping && <span className="showcase-muted block text-xs">+ free delivery</span>}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs">{when(c.start_at, "Immediately")}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs">{when(c.expiry_at, "Never")}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 tabular-nums">{usageText(c)}</td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/dashboard/admin/coupons/${c.id}`}
                        title="Edit coupon"
                        aria-label={`Edit coupon ${c.code}`}
                        className="icon-action flex h-9 w-9 items-center justify-center rounded-full"
                      >
                        <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setPendingDelete(c)}
                        title="Delete coupon"
                        aria-label={`Delete coupon ${c.code}`}
                        className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full"
                      >
                        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 md:hidden">
            {coupons.map((c) => (
              <li key={c.id} className="dashboard-card flex flex-col gap-2 rounded-2xl p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-mono text-sm font-semibold">{c.code}</p>
                    <p className="showcase-muted text-xs">
                      {amountText(c, currencySymbol)} · {COUPON_TYPE_LABEL[c.type] ?? c.type}
                    </p>
                  </div>
                  <StatusBadge status={c.status} />
                </div>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <dt className="showcase-muted">Start</dt>
                  <dd>{when(c.start_at, "Immediately")}</dd>
                  <dt className="showcase-muted">Expiry</dt>
                  <dd>{when(c.expiry_at, "Never")}</dd>
                  <dt className="showcase-muted">Usage</dt>
                  <dd className="tabular-nums">{usageText(c)}</dd>
                </dl>
                <div className="flex justify-end">
                  <Actions coupon={c} onDelete={setPendingDelete} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(next) => next !== page && load({ nextPage: next })} disabled={loading} />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Coupon?"
        description={pendingDelete ? `Are you sure you want to delete this coupon? "${pendingDelete.code}" will stop working.` : ""}
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}
