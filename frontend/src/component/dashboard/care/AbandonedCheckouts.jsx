"use client";

import { useEffect, useRef, useState } from "react";
import { FiPhone, FiSearch, FiUserX } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import formatPrice from "@/lib/formatPrice";
import { formatOrderDateTime, formatRelativeTime } from "@/lib/orderStatus";
import { careFetch } from "@/lib/careAdmin";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 20;

// Admin → Abandoned Checkouts (Module 14): people who typed a name and phone at checkout but didn't place an order
// (no activity for CHECKOUT_ABANDON_MINUTES — 30 by default). Placing an order with that phone removes them
// automatically. Dismiss the ones you've dealt with; "Dismissed" shows them again.
export default function AbandonedCheckouts({ initial, currencySymbol }) {
  const [rows, setRows] = useState(initial?.results ?? []);
  const [count, setCount] = useState(initial?.count ?? 0);
  const [view, setView] = useState("open"); // "open" | "dismissed"
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const requestId = useRef(0);
  const firstRender = useRef(true);
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const money = (v) => formatPrice(v, currencySymbol);

  async function load(nextPage, nextView = view, nextSearch = search) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page: String(nextPage), page_size: String(PAGE_SIZE) });
    if (nextView === "dismissed") params.set("status", "dismissed");
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    const res = await careFetch(`abandoned-checkouts?${params}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to load abandoned checkouts."));
    setRows(res.data.results ?? []);
    setCount(res.data.count ?? 0);
    setPage(nextPage);
  }

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return undefined;
    }
    const timer = setTimeout(() => load(1), 350);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  async function setStatus(lead, status) {
    setBusyId(lead.id);
    const res = await careFetch(`abandoned-checkouts/${lead.id}`, { method: "PATCH", body: { status } });
    setBusyId(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to update it."));
    setRows((list) => list.filter((l) => l.id !== lead.id));
    setCount((c) => Math.max(0, c - 1));
    notify.success(status === "dismissed" ? "Dismissed." : "Moved back to the list.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Abandoned Checkouts</h1>
        <p className="showcase-muted mt-1 text-sm">
          Shoppers who entered their name and phone at checkout but didn&apos;t place an order · {count}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,11rem)]">
        <div className="relative min-w-0">
          <label htmlFor="ac-search" className="sr-only">
            Search
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            id="ac-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, phone or email..."
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
        <label htmlFor="ac-view" className="sr-only">
          Show
        </label>
        <select
          id="ac-view"
          value={view}
          onChange={(e) => {
            setView(e.target.value);
            load(1, e.target.value);
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="open">To follow up</option>
          <option value="dismissed">Dismissed</option>
        </select>
      </div>

      {rows.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiUserX className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">{loading ? "Loading..." : "Nothing here"}</p>
          {!loading && view === "open" && <p className="showcase-muted text-sm">No abandoned checkouts to follow up right now.</p>}
        </div>
      ) : (
        <ul className={`grid gap-4 md:grid-cols-2 ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          {rows.map((lead) => (
            <li key={lead.id} className="dashboard-card flex flex-col gap-3 rounded-2xl p-5 text-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium">{lead.name || "No name given"}</p>
                  <a href={`tel:${lead.phone}`} className="inline-flex items-center gap-1 hover:underline">
                    <FiPhone className="h-3.5 w-3.5" aria-hidden="true" />
                    {lead.phone}
                  </a>
                  {lead.email && <p className="showcase-muted break-all text-xs">{lead.email}</p>}
                  {lead.district && <p className="showcase-muted text-xs">{lead.district}</p>}
                </div>
                <span className="font-semibold">{money(lead.cart_value)}</span>
              </div>
              {lead.cart_snapshot.length > 0 ? (
                <ul className="flex flex-col gap-1 border-t pt-3 text-xs">
                  {lead.cart_snapshot.map((item, i) => (
                    <li key={i} className="flex justify-between gap-3">
                      <span className="min-w-0 truncate">
                        {item.quantity} × {item.name}
                      </span>
                      <span>{money(item.price)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="showcase-muted border-t pt-3 text-xs">Cart was empty or unavailable.</p>
              )}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="showcase-muted text-xs" title={formatOrderDateTime(lead.updated_at)}>
                  Last seen {formatRelativeTime(lead.updated_at)}
                </span>
                <button
                  type="button"
                  onClick={() => setStatus(lead, view === "open" ? "dismissed" : "open")}
                  disabled={busyId === lead.id}
                  className="auth-btn auth-btn--outline rounded-full px-4 py-1.5 text-xs font-medium"
                >
                  {view === "open" ? "Dismiss" : "Restore"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(p) => p !== page && load(p)} disabled={loading} />
    </div>
  );
}
