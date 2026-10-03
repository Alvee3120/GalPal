"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiEdit2, FiPercent, FiPlus, FiSearch, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { errorText } from "@/lib/productAdmin";
import { formatOrderDateTime } from "@/lib/orderStatus";
import {
  DISCOUNT_KINDS,
  DISCOUNT_KIND_LABEL,
  DISCOUNT_STATUSES,
  DISCOUNT_STATUS_LABEL,
  DISCOUNT_TARGETS,
  DISCOUNT_TARGET_LABEL,
  discountFetch,
} from "@/lib/discountAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 10;
const SEARCH_DELAY_MS = 350;

const valueText = (d, symbol) => (d.kind === "percentage" ? `${Number(d.value)}%` : `${formatPrice(d.value, symbol)} OFF`);
const targetText = (d) =>
  d.target_type === "category"
    ? d.category?.name ?? "Deleted category"
    : `${d.product_count} product${d.product_count === 1 ? "" : "s"}`;

function StatusBadge({ status }) {
  // Same four states and colours as coupons (.coupon-status in globals.css).
  return (
    <span className="coupon-status rounded-full px-2.5 py-1 text-xs font-medium" data-status={status}>
      {DISCOUNT_STATUS_LABEL[status] ?? status}
    </span>
  );
}

function EditLink({ d }) {
  return (
    <Link href={`/dashboard/admin/discounts/${d.id}`} title="Edit discount" aria-label={`Edit discount ${d.name}`} className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
      <FiEdit2 className="h-4 w-4" aria-hidden="true" />
    </Link>
  );
}

function DeleteButton({ d, onDelete }) {
  return (
    <button type="button" onClick={() => onDelete(d)} title="Delete discount" aria-label={`Delete discount ${d.name}`} className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full">
      <FiTrash2 className="h-4 w-4" aria-hidden="true" />
    </button>
  );
}

// Admin → Discounts over /admin/discounts/ (apps.discounts — IsAdmin). Automatic price reductions on a category or on
// chosen products for a start–end window; prices are worked out by the backend everywhere. Search, status (active /
// scheduled / expired / inactive — from the switch, the dates and the current time), type and target filters run on the
// server with pagination.
export default function DiscountManagement({ initialDiscounts, initialCount, currencySymbol }) {
  const [discounts, setDiscounts] = useState(initialDiscounts);
  const [count, setCount] = useState(initialCount);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [target, setTarget] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const requestId = useRef(0);
  const lastSearch = useRef(""); // the search text the list currently reflects

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const filtered = Boolean(search.trim() || status || kind || target);

  async function load({ nextSearch = search, nextStatus = status, nextKind = kind, nextTarget = target, nextPage = 1 } = {}) {
    const id = ++requestId.current;
    setLoading(true);
    lastSearch.current = nextSearch.trim();
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    if (nextStatus) params.set("status", nextStatus);
    if (nextKind) params.set("kind", nextKind);
    if (nextTarget) params.set("target_type", nextTarget);
    const res = await discountFetch(`?${params.toString()}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) {
      if (res.status === 404 && nextPage > 1) return load({ nextSearch, nextStatus, nextKind, nextTarget, nextPage: nextPage - 1 });
      return notify.error(errorText(res, "Unable to load discounts. Please try again."));
    }
    setDiscounts(res.data.results ?? []);
    setCount(res.data.count ?? 0);
    setPage(nextPage);
  }

  // Reload only when the search text really changed — not on mount (the server already rendered the first page), and not
  // on React's development double-run of effects, which used to fire a needless request on page load.
  useEffect(() => {
    if (search.trim() === lastSearch.current) return undefined;
    const timer = setTimeout(() => load({ nextSearch: search }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  function clearFilters() {
    setSearch("");
    setStatus("");
    setKind("");
    setTarget("");
    load({ nextSearch: "", nextStatus: "", nextKind: "", nextTarget: "" });
  }

  async function confirmDelete() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    const res = await discountFetch(`/${pendingDelete.id}`, { method: "DELETE" });
    setDeleting(false);
    setPendingDelete(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the discount. Please try again."));
    notify.success("Discount deleted.");
    load({ nextPage: page });
  }

  const filterSelect = (id, label, value, setValue, options, key) => (
    <>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          load({ [key]: e.target.value });
        }}
        className="checkout-input rounded-lg px-3 py-2.5 text-sm"
      >
        <option value="">{label}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </>
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Discounts</h1>
          <p className="showcase-muted mt-1 text-sm">
            Automatic price reductions on a category or chosen products · {count} discount{count === 1 ? "" : "s"}
          </p>
        </div>
        <Link href="/dashboard/admin/discounts/new" className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          Add Discount
        </Link>
      </div>

      {/* A grid, not flex: .checkout-input is width:100%, so the grid sizes each control. */}
      <div className="grid grid-cols-1 gap-2 min-[480px]:grid-cols-3 lg:grid-cols-[minmax(0,1fr)_repeat(3,minmax(0,10rem))]">
        <div className="relative min-w-0 min-[480px]:col-span-3 lg:col-span-1">
          <label htmlFor="dc-search" className="sr-only">
            Search discounts
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input id="dc-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search discounts..." className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm" />
        </div>
        {filterSelect("dc-status", "All statuses", status, setStatus, DISCOUNT_STATUSES, "nextStatus")}
        {filterSelect("dc-kind", "All types", kind, setKind, DISCOUNT_KINDS, "nextKind")}
        {filterSelect("dc-target", "All targets", target, setTarget, DISCOUNT_TARGETS, "nextTarget")}
      </div>

      {discounts.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <FiPercent className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">{loading ? "Loading..." : filtered ? "No discounts match." : "No discounts yet"}</p>
          {!loading && filtered && (
            <button type="button" onClick={clearFilters} className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
              Clear filters
            </button>
          )}
        </div>
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[960px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Discount</th>
                  <th scope="col" className="px-4 py-3 font-medium">Type</th>
                  <th scope="col" className="px-4 py-3 font-medium">Value</th>
                  <th scope="col" className="px-4 py-3 font-medium">Target</th>
                  <th scope="col" className="px-4 py-3 font-medium">Applies To</th>
                  <th scope="col" className="px-4 py-3 font-medium">Start</th>
                  <th scope="col" className="px-4 py-3 font-medium">End</th>
                  <th scope="col" className="px-4 py-3 font-medium">Status</th>
                  <th scope="col" className="px-4 py-3 font-medium">Edit</th>
                  <th scope="col" className="px-4 py-3 font-medium">Delete</th>
                </tr>
              </thead>
              <tbody>
                {discounts.map((d) => (
                  <tr key={d.id}>
                    <td className="max-w-[14rem] px-4 py-3 font-semibold">{d.name}</td>
                    <td className="px-4 py-3">{DISCOUNT_KIND_LABEL[d.kind] ?? d.kind}</td>
                    <td className="whitespace-nowrap px-4 py-3 font-semibold tabular-nums">{valueText(d, currencySymbol)}</td>
                    <td className="px-4 py-3">{DISCOUNT_TARGET_LABEL[d.target_type] ?? d.target_type}</td>
                    <td className="px-4 py-3">{targetText(d)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs">{formatOrderDateTime(d.starts_at)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs">{formatOrderDateTime(d.ends_at)}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={d.status} />
                    </td>
                    <td className="px-4 py-3">
                      <EditLink d={d} />
                    </td>
                    <td className="px-4 py-3">
                      <DeleteButton d={d} onDelete={setPendingDelete} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 md:hidden">
            {discounts.map((d) => (
              <li key={d.id} className="dashboard-card flex flex-col gap-2 rounded-2xl p-4 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold">{d.name}</p>
                    <p className="showcase-muted text-xs">
                      {DISCOUNT_TARGET_LABEL[d.target_type]} · {targetText(d)}
                    </p>
                  </div>
                  <StatusBadge status={d.status} />
                </div>
                <p className="text-lg font-semibold tabular-nums">{valueText(d, currencySymbol)}</p>
                <p className="showcase-muted text-xs">
                  {formatOrderDateTime(d.starts_at)} → {formatOrderDateTime(d.ends_at)}
                </p>
                <div className="flex items-center justify-end gap-1.5">
                  <EditLink d={d} />
                  <DeleteButton d={d} onDelete={setPendingDelete} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(p) => p !== page && load({ nextPage: p })} disabled={loading} />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Discount?"
        description={`“${pendingDelete?.name ?? ""}” will be removed and prices go back to normal. Orders already placed keep their prices. To keep a record, edit it and switch it off instead.`}
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}
