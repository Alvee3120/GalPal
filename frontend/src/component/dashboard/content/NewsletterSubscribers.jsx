"use client";

import { useEffect, useRef, useState } from "react";
import { FiDownload, FiMail, FiSearch, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { formatOrderDateTime } from "@/lib/orderStatus";
import { contentFetch } from "@/lib/contentAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 20;

// Admin → Newsletter (Module 15): sign-ups from the storefront footer. Unsubscribe / resubscribe one person, delete,
// or download the current subscribers as CSV.
export default function NewsletterSubscribers({ initial }) {
  const [rows, setRows] = useState(initial?.results ?? []);
  const [count, setCount] = useState(initial?.count ?? 0);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const requestId = useRef(0);
  const firstRender = useRef(true);
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextPage, nextStatus = status, nextSearch = search) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page: String(nextPage), page_size: String(PAGE_SIZE) });
    if (nextStatus) params.set("is_subscribed", nextStatus);
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    const res = await contentFetch(`newsletter?${params}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to load subscribers."));
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

  async function toggle(row) {
    setBusyId(row.id);
    const res = await contentFetch(`newsletter/${row.id}`, { method: "PATCH", body: { is_subscribed: !row.is_subscribed } });
    setBusyId(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to update the subscriber."));
    setRows((list) => list.map((x) => (x.id === row.id ? res.data : x)));
  }

  async function confirmDelete() {
    const target = pendingDelete;
    setBusyId(target.id);
    const res = await contentFetch(`newsletter/${target.id}`, { method: "DELETE" });
    setBusyId(null);
    setPendingDelete(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the subscriber."));
    notify.success("Subscriber deleted.");
    load(rows.length === 1 && page > 1 ? page - 1 : page);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Newsletter</h1>
          <p className="showcase-muted mt-1 text-sm">Sign-ups from the storefront footer · {count}</p>
        </div>
        {/* A file download from the API proxy, not a page: a plain link with `download`, never client-side navigation. */}
        <a href="/api/admin/content/newsletter/export" download className="auth-btn auth-btn--outline inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiDownload className="h-4 w-4" aria-hidden="true" />
          Export CSV
        </a>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,11rem)]">
        <div className="relative min-w-0">
          <label htmlFor="nl-search" className="sr-only">
            Search
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input id="nl-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search email or phone..." className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm" />
        </div>
        <label htmlFor="nl-status" className="sr-only">
          Filter by status
        </label>
        <select
          id="nl-status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            load(1, e.target.value);
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All</option>
          <option value="true">Subscribed</option>
          <option value="false">Unsubscribed</option>
        </select>
      </div>

      {rows.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiMail className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">{loading ? "Loading..." : "No subscribers"}</p>
        </div>
      ) : (
        <div className={`dashboard-card overflow-x-auto rounded-2xl ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead>
              <tr className="showcase-muted text-xs uppercase tracking-wide">
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Phone</th>
                <th className="px-4 py-3 font-medium">Signed up</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-t">
                  <td className="break-all px-4 py-3">{row.email || "—"}</td>
                  <td className="px-4 py-3">{row.phone || "—"}</td>
                  <td className="px-4 py-3">
                    {formatOrderDateTime(row.created_at)}
                    {row.source && <span className="showcase-muted block text-xs">{row.source}</span>}
                  </td>
                  <td className="px-4 py-3">
                    <span className="product-status-badge rounded-full px-2.5 py-0.5 text-xs font-medium" data-status={row.is_subscribed ? "active" : "archived"}>
                      {row.is_subscribed ? "Subscribed" : "Unsubscribed"}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1.5">
                      <button type="button" onClick={() => toggle(row)} disabled={busyId === row.id} className="auth-btn auth-btn--outline rounded-full px-3 py-1.5 text-xs font-medium">
                        {row.is_subscribed ? "Unsubscribe" : "Resubscribe"}
                      </button>
                      <button type="button" onClick={() => setPendingDelete(row)} aria-label="Delete subscriber" title="Delete" className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full">
                        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(p) => p !== page && load(p)} disabled={loading} />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Subscriber?"
        description="Their sign-up will be removed completely."
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={Boolean(busyId)}
        onConfirm={confirmDelete}
        onCancel={() => !busyId && setPendingDelete(null)}
      />
    </div>
  );
}
