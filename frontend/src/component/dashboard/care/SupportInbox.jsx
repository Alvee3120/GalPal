"use client";

import { useEffect, useRef, useState } from "react";
import { FiInbox, FiMail, FiPhone, FiSearch } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { formatOrderDateTime } from "@/lib/orderStatus";
import { MESSAGE_STATUS, MESSAGE_STATUS_LABEL, careFetch } from "@/lib/careAdmin";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 20;
const STATUS_TONE = { new: "draft", in_progress: "active", resolved: "archived" };

function StatusBadge({ status }) {
  return (
    <span className="product-status-badge rounded-full px-2.5 py-0.5 text-xs font-medium" data-status={STATUS_TONE[status]}>
      {MESSAGE_STATUS_LABEL[status] ?? status}
    </span>
  );
}

// Admin → Support Inbox (Module 14): messages from the storefront contact form. Pick one to read it, add reply /
// working notes and move it New → In progress → Resolved. The actual reply goes out by phone or email.
export default function SupportInbox({ initial }) {
  const [rows, setRows] = useState(initial?.results ?? []);
  const [count, setCount] = useState(initial?.count ?? 0);
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const requestId = useRef(0);
  const firstRender = useRef(true);
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextPage, nextStatus = status, nextSearch = search) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page: String(nextPage), page_size: String(PAGE_SIZE) });
    if (nextStatus) params.set("status", nextStatus);
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    const res = await careFetch(`messages?${params}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to load the inbox."));
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

  function replace(message) {
    setSelected(message);
    setRows((list) => list.map((m) => (m.id === message.id ? message : m)));
  }

  async function changeStatus(next) {
    setSaving(true);
    const res = await careFetch(`messages/${selected.id}`, { method: "PATCH", body: { status: next } });
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to update the status."));
    replace(res.data);
    notify.success(`Marked ${MESSAGE_STATUS_LABEL[next]}.`);
  }

  async function addNote(e) {
    e.preventDefault();
    if (!note.trim()) return notify.error("Write a note first.");
    setSaving(true);
    const res = await careFetch(`messages/${selected.id}/notes`, { method: "POST", body: { text: note } });
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to add the note."));
    replace(res.data);
    setNote("");
    notify.success("Note added.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Support Inbox</h1>
        <p className="showcase-muted mt-1 text-sm">Messages from the website&apos;s contact form · {count} shown</p>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,11rem)]">
        <div className="relative min-w-0">
          <label htmlFor="si-search" className="sr-only">
            Search messages
          </label>
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            id="si-search"
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, phone, email or message..."
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
        </div>
        <label htmlFor="si-status" className="sr-only">
          Filter by status
        </label>
        <select
          id="si-status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            load(1, e.target.value);
          }}
          className="checkout-input rounded-lg px-3 py-2.5 text-sm"
        >
          <option value="">All statuses</option>
          {MESSAGE_STATUS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:items-start">
        <div className={`flex flex-col gap-3 ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          {rows.length === 0 ? (
            <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
              <FiInbox className="showcase-muted h-8 w-8" aria-hidden="true" />
              <p className="custom-font text-xl">{loading ? "Loading..." : "No messages"}</p>
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {rows.map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(m)}
                    aria-pressed={selected?.id === m.id}
                    className="care-row dashboard-card flex w-full flex-col gap-1 rounded-2xl p-4 text-left text-sm"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium">{m.name}</span>
                      <StatusBadge status={m.status} />
                    </span>
                    <span className="truncate">{m.subject || m.message}</span>
                    <span className="showcase-muted text-xs">{formatOrderDateTime(m.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <DashboardPagination page={page} totalPages={totalPages} onPageChange={(p) => p !== page && load(p)} disabled={loading} />
        </div>

        <section className="dashboard-card rounded-2xl p-5 sm:p-6 lg:sticky lg:top-24" aria-live="polite">
          {!selected ? (
            <p className="showcase-muted py-10 text-center text-sm">Select a message to read it.</p>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="custom-font text-xl">{selected.subject || "Message"}</h2>
                  <p className="showcase-muted text-xs">{formatOrderDateTime(selected.created_at)}</p>
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <span className="sr-only">Status</span>
                  <select
                    value={selected.status}
                    onChange={(e) => changeStatus(e.target.value)}
                    disabled={saving}
                    className="checkout-input rounded-lg px-3 py-2 text-sm"
                  >
                    {MESSAGE_STATUS.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
                <span className="font-medium">{selected.name}</span>
                {selected.phone && (
                  <a href={`tel:${selected.phone}`} className="inline-flex items-center gap-1 hover:underline">
                    <FiPhone className="h-3.5 w-3.5" aria-hidden="true" />
                    {selected.phone}
                  </a>
                )}
                {selected.email && (
                  <a href={`mailto:${selected.email}`} className="inline-flex items-center gap-1 break-all hover:underline">
                    <FiMail className="h-3.5 w-3.5" aria-hidden="true" />
                    {selected.email}
                  </a>
                )}
              </div>
              <p className="whitespace-pre-line rounded-xl border p-4 text-sm">{selected.message}</p>

              <div>
                <h3 className="text-sm font-semibold">Notes</h3>
                {selected.notes.length === 0 ? (
                  <p className="showcase-muted mt-1 text-xs">No notes yet.</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-2">
                    {selected.notes.map((n) => (
                      <li key={n.id} className="text-sm">
                        <p className="whitespace-pre-line">{n.text}</p>
                        <p className="showcase-muted text-xs">
                          {n.author?.full_name ?? "Staff"} · {formatOrderDateTime(n.created_at)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
                <form onSubmit={addNote} className="mt-3 flex flex-col gap-2">
                  <label htmlFor="si-note" className="sr-only">
                    Add a note
                  </label>
                  <textarea
                    id="si-note"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    rows={3}
                    maxLength={2000}
                    placeholder="e.g. Called back, sent the price list by WhatsApp."
                    className="checkout-input w-full rounded-lg px-3 py-2.5 text-sm"
                  />
                  <button type="submit" disabled={saving} className="auth-btn auth-btn--primary w-fit rounded-full px-5 py-2 text-sm font-medium">
                    {saving ? "Saving…" : "Add Note"}
                  </button>
                </form>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
