"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiBell, FiRefreshCw, FiSearch } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { formatOrderDateTime } from "@/lib/orderStatus";
import { CHANNEL_LABEL, EVENT_LABEL, LOG_STATUS_LABEL, LOG_STATUS_TONE, notificationsFetch } from "@/lib/notificationsAdmin";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 20;

// Admin → Notifications (Module 16): every email and SMS the shop sent, with its status and attempts. Codes and
// passwords are masked by the backend. A failed message can be re-sent unless it held a code/password.
export default function NotificationLog({ initial }) {
  const [rows, setRows] = useState(initial?.results ?? []);
  const [count, setCount] = useState(initial?.count ?? 0);
  const [filters, setFilters] = useState({ event: "", channel: "", status: "" });
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const requestId = useRef(0);
  const firstRender = useRef(true);
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextPage, nextFilters = filters, nextSearch = search) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page: String(nextPage), page_size: String(PAGE_SIZE) });
    Object.entries(nextFilters).forEach(([k, v]) => v && params.set(k, v));
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    const res = await notificationsFetch(`logs?${params}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to load notifications."));
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

  function setFilter(key, value) {
    const next = { ...filters, [key]: value };
    setFilters(next);
    load(1, next);
  }

  async function retry(row) {
    setBusyId(row.id);
    const res = await notificationsFetch(`logs/${row.id}/retry`, { method: "POST" });
    setBusyId(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to re-send."));
    setRows((list) => list.map((x) => (x.id === row.id ? res.data : x)));
    notify.success(res.data.status === "sent" ? "Sent." : "Queued to send again.");
  }

  const select = (key, label, options) => (
    <>
      <label htmlFor={`nl-${key}`} className="sr-only">
        {label}
      </label>
      <select id={`nl-${key}`} value={filters[key]} onChange={(e) => setFilter(key, e.target.value)} className="checkout-input rounded-lg px-3 py-2.5 text-sm">
        <option value="">{label}</option>
        {Object.entries(options).map(([value, text]) => (
          <option key={value} value={value}>
            {text}
          </option>
        ))}
      </select>
    </>
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Notifications</h1>
        <p className="showcase-muted mt-1 text-sm">Every email and SMS sent to customers and admins · {count}</p>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-[minmax(0,1fr)_repeat(3,minmax(0,11rem))]">
        <div className="relative min-w-0">
          <label htmlFor="nl-search" className="sr-only">
            Search
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input id="nl-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search recipient or order number..." className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm" />
        </div>
        {select("event", "All events", EVENT_LABEL)}
        {select("channel", "All channels", CHANNEL_LABEL)}
        {select("status", "All statuses", LOG_STATUS_LABEL)}
      </div>

      {rows.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiBell className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">{loading ? "Loading..." : "No notifications"}</p>
        </div>
      ) : (
        <ul className={`flex flex-col gap-3 ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          {rows.map((row) => (
            <li key={row.id} className="dashboard-card rounded-2xl p-4 text-sm sm:p-5">
              <div className="flex flex-wrap items-center gap-3">
                <button type="button" onClick={() => setOpenId(openId === row.id ? null : row.id)} aria-expanded={openId === row.id} className="min-w-0 flex-1 text-left">
                  <span className="font-semibold">{row.event_label ?? EVENT_LABEL[row.event]}</span>
                  <span className="showcase-muted"> · {CHANNEL_LABEL[row.channel]} to </span>
                  <span className="break-all">{row.recipient}</span>
                  <span className="showcase-muted block text-xs">
                    {formatOrderDateTime(row.created_at)} · {row.attempts} attempt{row.attempts === 1 ? "" : "s"}
                    {row.subject && ` · ${row.subject}`}
                  </span>
                </button>
                {row.order && (
                  <Link href={`/dashboard/admin/orders/${row.order}`} className="text-xs font-medium hover:underline">
                    Order {row.order_number}
                  </Link>
                )}
                <span className="product-status-badge rounded-full px-2.5 py-0.5 text-xs font-medium" data-status={LOG_STATUS_TONE[row.status]}>
                  {LOG_STATUS_LABEL[row.status] ?? row.status}
                </span>
                {row.status === "failed" && !row.has_secret && (
                  <button type="button" onClick={() => retry(row)} disabled={busyId === row.id} className="auth-btn auth-btn--outline inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium">
                    <FiRefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                    {busyId === row.id ? "Sending…" : "Re-send"}
                  </button>
                )}
              </div>
              {openId === row.id && (
                <div className="mt-3 border-t pt-3">
                  <p className="whitespace-pre-line">{row.body}</p>
                  {row.error && <p className="mt-2 text-xs text-[color:var(--color-danger)]">Last error: {row.error}</p>}
                  {row.has_secret && <p className="showcase-muted mt-2 text-xs">Contained a code or password (masked here; can&apos;t be re-sent).</p>}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(p) => p !== page && load(p)} disabled={loading} />
    </div>
  );
}
