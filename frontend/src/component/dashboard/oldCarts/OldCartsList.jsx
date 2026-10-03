"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiSearch, FiShoppingCart } from "react-icons/fi";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { formatOrderDateTime, formatRelativeTime } from "@/lib/orderStatus";
import { useStaffHref } from "@/lib/staffPaths";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 20;
const SEARCH_DELAY_MS = 350;
const AGE_OPTIONS = [
  { value: "", label: "All ages" },
  { value: "6_24", label: "6–24 hours" },
  { value: "1_3", label: "1–3 days" },
  { value: "3_plus", label: "3+ days" },
];

// Old Carts (Admin + CCE): customers whose cart has held an item for more than 6 hours, oldest first. Everything —
// which carts are old, search, the age filter, paging — is decided by the backend (GET /admin/orders/old-carts/);
// this page only shows it. Read-only: nothing here changes a customer's cart.
export default function OldCartsList({ initial, currencySymbol }) {
  const to = useStaffHref();
  const [rows, setRows] = useState(initial?.results ?? []);
  const [count, setCount] = useState(initial?.count ?? 0);
  const [customers, setCustomers] = useState(initial?.customers_with_old_carts ?? 0);
  const [search, setSearch] = useState("");
  const [age, setAge] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const requestId = useRef(0);
  const firstRender = useRef(true);
  const money = (v) => formatPrice(v, currencySymbol);
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextSearch, nextPage, nextAge = age) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    if (nextAge) params.set("age", nextAge);
    try {
      const res = await fetch(`/api/admin/orders/old-carts?${params}`, { cache: "no-store" });
      const data = await res.json().catch(() => null);
      if (id !== requestId.current) return;
      if (!res.ok) {
        if (res.status === 404 && nextPage > 1) return load(nextSearch, 1, nextAge);
        notify.error("Unable to load old carts. Please try again.");
        return;
      }
      setRows(data.results ?? []);
      setCount(data.count ?? 0);
      setCustomers(data.customers_with_old_carts ?? 0);
      setPage(nextPage);
    } catch {
      if (id === requestId.current) notify.error("Unable to load old carts. Please try again.");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
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

  const detailHref = (row) => to(`/dashboard/CCE/old-carts/${row.id}`);
  const filtered = Boolean(search.trim() || age);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Old Carts</h1>
        <p className="showcase-muted mt-1 text-sm">
          {customers} customer{customers === 1 ? "" : "s"} with cart items older than 6 hours. For follow-up only — carts
          are never changed here.
        </p>
      </div>

      {/* A grid, not flex: .checkout-input is width:100%, so the grid (not a w-* class) sizes each control. */}
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,11rem)]">
        <div className="relative min-w-0">
          <label htmlFor="oc-search" className="sr-only">
            Search old carts
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            id="oc-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by customer, phone, email or product..."
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
        <label htmlFor="oc-age" className="sr-only">
          Filter by cart age
        </label>
        <select
          id="oc-age"
          value={age}
          onChange={(e) => {
            setAge(e.target.value);
            load(search, 1, e.target.value);
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          {AGE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      {rows.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiShoppingCart className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">{loading ? "Loading..." : "No old carts"}</p>
          {!loading && (
            <p className="showcase-muted text-sm">
              {filtered ? "Try a different search or filter." : "No customer has kept an item in their cart for more than 6 hours."}
            </p>
          )}
        </div>
      ) : (
        <div className={loading ? "opacity-60 transition-opacity" : ""} aria-busy={loading}>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[880px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Customer</th>
                  <th scope="col" className="px-4 py-3 font-medium">Items</th>
                  <th scope="col" className="px-4 py-3 font-medium">Cart Value</th>
                  <th scope="col" className="px-4 py-3 font-medium">Oldest Item</th>
                  <th scope="col" className="px-4 py-3 font-medium">Last Updated</th>
                  <th scope="col" className="px-4 py-3 font-medium">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3">
                      <p className="font-medium">{row.customer.name}</p>
                      <p className="showcase-muted text-xs">{row.customer.phone}</p>
                      {row.customer.email && <p className="showcase-muted text-xs">{row.customer.email}</p>}
                    </td>
                    <td className="px-4 py-3">
                      {row.line_count} product{row.line_count === 1 ? "" : "s"}
                      <p className="showcase-muted text-xs">
                        {row.quantity} unit{row.quantity === 1 ? "" : "s"} · {row.old_line_count} older than 6h
                      </p>
                      {row.out_of_stock_count > 0 && (
                        <span className="product-status-badge mt-1 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium" data-status="archived">
                          {row.out_of_stock_count} out of stock
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-medium">{money(row.cart_value)}</td>
                    <td className="px-4 py-3">
                      <span className="font-medium">{formatRelativeTime(row.oldest_item_at)}</span>
                      <p className="showcase-muted text-xs">{formatOrderDateTime(row.oldest_item_at)}</p>
                    </td>
                    <td className="showcase-muted px-4 py-3 text-xs">{formatOrderDateTime(row.last_activity_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link href={detailHref(row)} className="auth-btn auth-btn--outline rounded-full px-4 py-1.5 text-xs font-medium">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 md:hidden">
            {rows.map((row) => (
              <li key={row.id} className="dashboard-card flex flex-col gap-2 rounded-2xl p-4 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium">{row.customer.name}</p>
                    <p className="showcase-muted text-xs">{row.customer.phone}</p>
                  </div>
                  <span className="font-semibold">{money(row.cart_value)}</span>
                </div>
                <p className="showcase-muted text-xs">
                  {row.line_count} product{row.line_count === 1 ? "" : "s"} · {row.quantity} unit{row.quantity === 1 ? "" : "s"} · oldest added{" "}
                  {formatRelativeTime(row.oldest_item_at)}
                  {row.out_of_stock_count > 0 && ` · ${row.out_of_stock_count} out of stock`}
                </p>
                <Link href={detailHref(row)} className="auth-btn auth-btn--outline w-fit rounded-full px-4 py-1.5 text-xs font-medium">
                  View Cart
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(next) => next !== page && load(search, next)} disabled={loading} />
    </div>
  );
}
