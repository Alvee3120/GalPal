"use client";

import { useEffect, useRef, useState } from "react";
import { FiSearch, FiShield } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { formatOrderDateTime } from "@/lib/orderStatus";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 25;

// Readable names for the event entries (apps.audit.signals / order services); request entries show method + path.
const ACTION_LABEL = {
  "order.created": "Created a manual order",
  "order.status_changed": "Changed order status",
  "order.note_added": "Added an order note",
  "order.shipping_override": "Overrode the shipping charge",
  "order.edited": "Edited an order",
  "shipping.zone_charge_changed": "Changed a delivery charge",
};
const ROLE_LABEL = { admin: "Admin", cce: "CCE", customer: "Customer" };

function Changes({ changes }) {
  const entries = Object.entries(changes ?? {});
  if (!entries.length) return null;
  return (
    <ul className="mt-2 flex flex-col gap-1 text-xs">
      {entries.map(([field, [before, after]]) => (
        <li key={field}>
          <span className="font-medium">{field}</span>: <span className="showcase-muted line-through">{String(before ?? "—")}</span> → <span>{String(after ?? "—")}</span>
        </li>
      ))}
    </ul>
  );
}

// Admin → Audit Log (Module 18): who did what, when and from which IP — every Admin/CCE write (request entries) and
// the key business events with before/after (event entries). Read-only; passwords and tokens are redacted by the backend.
export default function AuditLog({ initial }) {
  const [rows, setRows] = useState(initial?.results ?? []);
  const [count, setCount] = useState(initial?.count ?? 0);
  const [kind, setKind] = useState("event");
  const [role, setRole] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [openId, setOpenId] = useState(null);
  const requestId = useRef(0);
  const firstRender = useRef(true);
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextPage, next = {}) {
    const k = next.kind ?? kind;
    const r = next.role ?? role;
    const q = next.search ?? search;
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page: String(nextPage), page_size: String(PAGE_SIZE) });
    if (k) params.set("kind", k);
    if (r) params.set("actor_role", r);
    if (q.trim()) params.set("search", q.trim());
    try {
      const res = await fetch(`/api/admin/audit-logs?${params}`, { cache: "no-store" });
      const data = await res.json().catch(() => null);
      if (id !== requestId.current) return;
      if (!res.ok) return notify.error(data?.error?.message ?? "Unable to load the audit log.");
      setRows(data.results ?? []);
      setCount(data.count ?? 0);
      setPage(nextPage);
    } catch {
      if (id === requestId.current) notify.error("Unable to load the audit log.");
    } finally {
      if (id === requestId.current) setLoading(false);
    }
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

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Audit Log</h1>
        <p className="showcase-muted mt-1 text-sm">Who changed what, and from where · {count}</p>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,12rem)_minmax(0,10rem)]">
        <div className="relative min-w-0">
          <label htmlFor="audit-search" className="sr-only">
            Search
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input id="audit-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search staff, order, path or IP..." className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm" />
        </div>
        <label htmlFor="audit-kind" className="sr-only">
          Entry type
        </label>
        <select
          id="audit-kind"
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            load(1, { kind: e.target.value });
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="event">Key events</option>
          <option value="request">All write requests</option>
          <option value="">Everything</option>
        </select>
        <label htmlFor="audit-role" className="sr-only">
          Role
        </label>
        <select
          id="audit-role"
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            load(1, { role: e.target.value });
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All staff</option>
          <option value="admin">Admin</option>
          <option value="cce">CCE</option>
        </select>
      </div>

      {rows.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiShield className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">{loading ? "Loading..." : "Nothing logged yet"}</p>
        </div>
      ) : (
        <ul className={`flex flex-col gap-2 ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          {rows.map((row) => {
            const isRequest = row.action.startsWith("api.");
            const failed = isRequest && row.status_code >= 400;
            return (
              <li key={row.id} className="dashboard-card rounded-2xl p-4 text-sm">
                <button type="button" onClick={() => setOpenId(openId === row.id ? null : row.id)} aria-expanded={openId === row.id} className="flex w-full flex-wrap items-baseline gap-x-3 gap-y-1 text-left">
                  <span className="font-semibold">{row.actor_name || "System"}</span>
                  <span className="showcase-muted text-xs">{ROLE_LABEL[row.actor_role] ?? row.actor_role}</span>
                  <span className="min-w-0 flex-1">
                    {isRequest ? (
                      <code className="break-all text-xs">
                        {row.method} {row.path}
                      </code>
                    ) : (
                      <>
                        {ACTION_LABEL[row.action] ?? row.action}
                        {row.target_label && <span className="font-medium"> · {row.target_label}</span>}
                      </>
                    )}
                  </span>
                  {isRequest && (
                    <span className="product-status-badge rounded-full px-2 py-0.5 text-xs font-medium" data-status={failed ? "archived" : "active"}>
                      {row.status_code}
                    </span>
                  )}
                  <span className="showcase-muted text-xs">
                    {formatOrderDateTime(row.created_at)}
                    {row.ip_address && ` · ${row.ip_address}`}
                  </span>
                </button>
                {!isRequest && <Changes changes={row.changes} />}
                {openId === row.id && (
                  <pre className="content-preview mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg text-xs">{JSON.stringify({ changes: row.changes, ...row.metadata, user_agent: row.user_agent }, null, 2)}</pre>
                )}
              </li>
            );
          })}
        </ul>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(p) => p !== page && load(p)} disabled={loading} />
    </div>
  );
}
