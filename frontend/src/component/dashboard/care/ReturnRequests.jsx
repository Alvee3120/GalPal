"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiRotateCcw, FiSearch } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import formatPrice from "@/lib/formatPrice";
import { formatOrderDateTime } from "@/lib/orderStatus";
import { RETURN_NEXT, RETURN_REASON_LABEL, RETURN_STATUS_LABEL, careFetch } from "@/lib/careAdmin";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 20;
const TONE = { requested: "draft", approved: "active", received: "active", refunded: "archived", rejected: "archived" };

// Admin → Return Requests (Module 14): customers' return/refund requests on delivered orders. Move each one through
// Requested → Approved → Item received → Refunded / replaced (or Rejected), with a note the customer sees on their
// order. Refunding the money itself is done in Payments.
export default function ReturnRequests({ initial, currencySymbol }) {
  const [rows, setRows] = useState(initial?.results ?? []);
  const [count, setCount] = useState(initial?.count ?? 0);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [drafts, setDrafts] = useState({}); // id -> { status, admin_note }
  const [busyId, setBusyId] = useState(null);
  const requestId = useRef(0);
  const firstRender = useRef(true);
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextPage, nextStatus = status, nextSearch = search) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page: String(nextPage), page_size: String(PAGE_SIZE) });
    if (nextStatus) params.set("status", nextStatus);
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    const res = await careFetch(`returns?${params}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to load return requests."));
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

  const draftOf = (r) => drafts[r.id] ?? { status: r.status, admin_note: r.admin_note };
  const setDraft = (r, patch) => setDrafts((d) => ({ ...d, [r.id]: { ...draftOf(r), ...patch } }));

  async function save(r) {
    const draft = draftOf(r);
    setBusyId(r.id);
    const res = await careFetch(`returns/${r.id}`, { method: "PATCH", body: draft });
    setBusyId(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to update the request."));
    setRows((list) => list.map((x) => (x.id === r.id ? res.data : x)));
    setDrafts((d) => {
      const next = { ...d };
      delete next[r.id];
      return next;
    });
    notify.success("Return request updated.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Return Requests</h1>
        <p className="showcase-muted mt-1 text-sm">Customers&apos; return / refund requests on delivered orders · {count}</p>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,11rem)]">
        <div className="relative min-w-0">
          <label htmlFor="rr-search" className="sr-only">
            Search
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            id="rr-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search order number, phone or name..."
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
        <label htmlFor="rr-status" className="sr-only">
          Filter by status
        </label>
        <select
          id="rr-status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            load(1, e.target.value);
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All statuses</option>
          {Object.entries(RETURN_STATUS_LABEL).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {rows.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiRotateCcw className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">{loading ? "Loading..." : "No return requests"}</p>
        </div>
      ) : (
        <ul className={`flex flex-col gap-4 ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          {rows.map((r) => {
            const draft = draftOf(r);
            const next = RETURN_NEXT[r.status] ?? [];
            const changed = draft.status !== r.status || (draft.admin_note ?? "") !== (r.admin_note ?? "");
            return (
              <li key={r.id} className="dashboard-card flex flex-col gap-4 rounded-2xl p-5 text-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <Link href={`/dashboard/admin/orders/${r.order.id}`} className="font-semibold hover:underline">
                      Order {r.order.number}
                    </Link>
                    <p className="showcase-muted text-xs">
                      {r.customer.full_name} · {r.customer.phone} · {formatPrice(r.order.grand_total, currencySymbol)}
                    </p>
                  </div>
                  <span className="product-status-badge rounded-full px-2.5 py-0.5 text-xs font-medium" data-status={TONE[r.status]}>
                    {RETURN_STATUS_LABEL[r.status] ?? r.status}
                  </span>
                </div>
                <div>
                  <p className="font-medium">{RETURN_REASON_LABEL[r.reason] ?? r.reason}</p>
                  <p className="mt-1 whitespace-pre-line">{r.details}</p>
                  <p className="showcase-muted mt-1 text-xs">
                    Requested {formatOrderDateTime(r.created_at)}
                    {r.handled_by && ` · last handled by ${r.handled_by.full_name}`}
                  </p>
                </div>
                <div className="grid gap-3 border-t pt-4 sm:grid-cols-[12rem_minmax(0,1fr)_auto] sm:items-end">
                  <label className="flex flex-col gap-1.5">
                    <span className="text-xs font-medium">Status</span>
                    <select
                      value={draft.status}
                      onChange={(e) => setDraft(r, { status: e.target.value })}
                      disabled={next.length === 0}
                      className="checkout-input rounded-lg px-3 py-2 text-sm"
                    >
                      <option value={r.status}>{RETURN_STATUS_LABEL[r.status]}</option>
                      {next.map((s) => (
                        <option key={s} value={s}>
                          {RETURN_STATUS_LABEL[s]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex min-w-0 flex-col gap-1.5">
                    <span className="text-xs font-medium">Note to the customer</span>
                    <input
                      value={draft.admin_note ?? ""}
                      onChange={(e) => setDraft(r, { admin_note: e.target.value })}
                      maxLength={2000}
                      placeholder="e.g. We'll pick it up tomorrow."
                      className="checkout-input w-full rounded-lg px-3 py-2 text-sm"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={() => save(r)}
                    disabled={!changed || busyId === r.id}
                    className="auth-btn auth-btn--primary rounded-full px-5 py-2 text-sm font-medium"
                  >
                    {busyId === r.id ? "Saving…" : "Save"}
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(p) => p !== page && load(p)} disabled={loading} />
    </div>
  );
}
