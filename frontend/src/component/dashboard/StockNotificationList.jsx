"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiSearch } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { formatOrderDateTime } from "@/lib/orderStatus";
import { catalogFetch, errorText } from "@/lib/productAdmin";
import ProductImage from "@/component/shared/ProductImage";
import DashboardPagination from "./DashboardPagination";

const PAGE_SIZE = 10;
const SEARCH_DELAY_MS = 350;
const TABS = [
  { value: "waiting", label: "Waiting" },
  { value: "notified", label: "Notified" },
  { value: "", label: "All" },
];

// Waiting (the default for a new request) / Notified, changeable by staff — e.g. after phoning the customer
// themselves, or to put a request back so the automatic SMS goes out on the next restock.
function StatusSelect({ row, busy, onChange }) {
  return (
    <select
      value={row.status}
      onChange={(e) => onChange(row, e.target.value)}
      disabled={busy}
      aria-label={`Status of the request from ${row.phone}`}
      data-status={row.status === "notified" ? "active" : "draft"}
      className="product-status-badge status-select cursor-pointer rounded-full py-1 pl-3 pr-2 text-xs font-medium disabled:opacity-60"
    >
      <option value="waiting">Waiting</option>
      <option value="notified">Notified</option>
    </select>
  );
}

function ProductCell({ row }) {
  return (
    <div className="flex min-w-0 items-center gap-3">
      <div className="cart-thumb relative h-12 w-12 shrink-0 overflow-hidden rounded-lg">
        <ProductImage src={row.product.feature_image} alt="" tight />
      </div>
      <div className="min-w-0">
        <Link href={`/dashboard/CCE/products/${row.product.id}`} className="font-medium leading-snug hover:underline">
          {row.product.name}
        </Link>
        <p className="showcase-muted text-xs">
          {row.variant ? `${row.variant.label || "Variant"} · ${row.variant.sku}` : row.product.sku}
        </p>
      </div>
    </div>
  );
}

// Notify Me requests (apps.catalog.models.StockNotification) via the staff list endpoint
// (GET /admin/stock-notifications/, IsCatalogStaff): who asked to be texted when an item is back, and whether
// the SMS has gone out. Alerts send themselves when stock is added (apps.catalog.services.adjust_stock); staff can
// also flip a request between Waiting and Notified by hand (PATCH /admin/stock-notifications/<id>/).
export default function StockNotificationList({ initialRows, initialCount }) {
  const [rows, setRows] = useState(initialRows);
  const [count, setCount] = useState(initialCount);
  const [status, setStatus] = useState("waiting");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState(null);
  const requestId = useRef(0);
  const firstRender = useRef(true);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextStatus, nextSearch, nextPage) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
    if (nextStatus) params.set("status", nextStatus);
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    const res = await catalogFetch(`stock-notifications?${params.toString()}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) {
      notify.error(errorText(res, "Unable to load Notify Me requests. Please try again."));
      return;
    }
    setRows(res.data.results ?? []);
    setCount(res.data.count ?? 0);
    setPage(nextPage);
  }

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = setTimeout(() => load(status, search, 1), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  function changeTab(next) {
    if (next === status) return;
    setStatus(next);
    load(next, search, 1);
  }

  async function changeStatus(row, next) {
    if (next === row.status || savingId) return;
    setSavingId(row.id);
    const res = await catalogFetch(`stock-notifications/${row.id}`, { method: "PATCH", body: { status: next } });
    setSavingId(null);
    if (!res.ok) {
      notify.error(errorText(res, "Unable to update the request. Please try again."));
      return;
    }
    notify.success(next === "notified" ? "Marked as notified." : "Marked as waiting.");
    if (status && res.data.status !== status) {
      // It no longer belongs in this tab: drop it and keep the count honest.
      setRows((list) => list.filter((r) => r.id !== row.id));
      setCount((c) => Math.max(0, c - 1));
    } else {
      setRows((list) => list.map((r) => (r.id === row.id ? res.data : r)));
    }
  }

  const who = (row) => row.customer_name || "Guest";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Notify Me Requests</h1>
        <p className="showcase-muted mt-1 text-sm">Customers waiting for an item to be back in stock. They&apos;re texted automatically when stock is added, or mark them Notified yourself.</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div role="tablist" aria-label="Request status" className="flex gap-1.5">
          {TABS.map((tab) => (
            <button
              key={tab.value || "all"}
              type="button"
              role="tab"
              aria-selected={status === tab.value}
              onClick={() => changeTab(tab.value)}
              className={`auth-btn rounded-full px-4 py-2 text-xs font-medium ${status === tab.value ? "auth-btn--primary" : "auth-btn--outline"}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="relative min-w-0 flex-1">
          <label htmlFor="sn-search" className="sr-only">
            Search Notify Me requests
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            id="sn-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search phone, customer, product or SKU..."
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
      </div>

      <p className="showcase-muted -mt-2 text-sm">
        {count} request{count === 1 ? "" : "s"}
      </p>

      {rows.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">{loading ? "Loading..." : "No requests found"}</p>
          {!loading && <p className="showcase-muted text-sm">{search.trim() ? "Try a different search." : "Nobody is waiting in this list right now."}</p>}
        </div>
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Product</th>
                  <th scope="col" className="px-4 py-3 font-medium">Customer</th>
                  <th scope="col" className="px-4 py-3 font-medium">Requested</th>
                  <th scope="col" className="px-4 py-3 font-medium">Status</th>
                  <th scope="col" className="px-4 py-3 font-medium">Stock Now</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3">
                      <ProductCell row={row} />
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium">{who(row)}</p>
                      <a href={`tel:${row.phone}`} className="showcase-muted text-xs hover:underline">
                        {row.phone}
                      </a>
                    </td>
                    <td className="px-4 py-3 text-xs">{formatOrderDateTime(row.created_at)}</td>
                    <td className="px-4 py-3">
                      <StatusSelect row={row} busy={savingId === row.id} onChange={changeStatus} />
                      {row.notified_at && <p className="showcase-muted mt-1 text-xs">{formatOrderDateTime(row.notified_at)}</p>}
                    </td>
                    <td className="px-4 py-3 text-xs">{row.in_stock_now ? "In stock" : <span className="showcase-muted">Out of stock</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 md:hidden">
            {rows.map((row) => (
              <li key={row.id} className="dashboard-card flex flex-col gap-3 rounded-2xl p-4">
                <div className="flex items-start justify-between gap-2">
                  <ProductCell row={row} />
                  <StatusSelect row={row} busy={savingId === row.id} onChange={changeStatus} />
                </div>
                <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <dt className="showcase-muted">Customer</dt>
                  <dd>
                    {who(row)} ·{" "}
                    <a href={`tel:${row.phone}`} className="hover:underline">
                      {row.phone}
                    </a>
                  </dd>
                  <dt className="showcase-muted">Requested</dt>
                  <dd>{formatOrderDateTime(row.created_at)}</dd>
                  {row.notified_at && (
                    <>
                      <dt className="showcase-muted">Notified</dt>
                      <dd>{formatOrderDateTime(row.notified_at)}</dd>
                    </>
                  )}
                  <dt className="showcase-muted">Stock now</dt>
                  <dd>{row.in_stock_now ? "In stock" : "Out of stock"}</dd>
                </dl>
              </li>
            ))}
          </ul>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(next) => next !== page && load(status, search, next)} disabled={loading} />
    </div>
  );
}
