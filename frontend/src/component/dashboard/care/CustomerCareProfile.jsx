"use client";

import { useState } from "react";
import Link from "next/link";
import { FiArrowLeft, FiMail, FiPhone, FiTrash2, FiX } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import formatPrice from "@/lib/formatPrice";
import { STATUS_LABEL, formatOrderDateTime } from "@/lib/orderStatus";
import { careFetch } from "@/lib/careAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import UserAvatar from "../users/UserAvatar";

// Admin → Customer Care profile (Module 14): one customer's account, order stats (total spent leaves out cancelled,
// failed and returned orders — computed by the backend), tags (VIP, Risky…), internal care notes and recent orders.
// Notes and tags are staff-only; the customer never sees them.
export default function CustomerCareProfile({ initial, currencySymbol, tagOptions = [] }) {
  const [profile, setProfile] = useState(initial);
  const [note, setNote] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const money = (v) => formatPrice(v, currencySymbol);
  const tags = profile.tags.map((t) => t.name);
  const suggestions = tagOptions.filter((t) => !tags.some((x) => x.toLowerCase() === t.name.toLowerCase()));

  async function saveTags(next) {
    setBusy(true);
    const res = await careFetch(`customers/${profile.id}/tags`, { method: "PUT", body: { tags: next } });
    setBusy(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to update tags."));
    setProfile((p) => ({ ...p, tags: res.data }));
    setTagInput("");
  }

  async function addNote(e) {
    e.preventDefault();
    if (!note.trim()) return notify.error("Write a note first.");
    setBusy(true);
    const res = await careFetch(`customers/${profile.id}/notes`, { method: "POST", body: { text: note } });
    setBusy(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to add the note."));
    setProfile((p) => ({ ...p, notes: [res.data, ...p.notes] }));
    setNote("");
    notify.success("Note added.");
  }

  async function deleteNote() {
    const target = pendingDelete;
    if (!target) return;
    setBusy(true);
    const res = await careFetch(`notes/${target.id}`, { method: "DELETE" });
    setBusy(false);
    setPendingDelete(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the note."));
    setProfile((p) => ({ ...p, notes: p.notes.filter((n) => n.id !== target.id) }));
    notify.success("Note deleted.");
  }

  const stats = profile.stats;
  return (
    <div className="flex flex-col gap-6">
      <Link href="/dashboard/admin/users" className="showcase-muted inline-flex w-fit items-center gap-1.5 text-sm hover:text-current">
        <FiArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to Users
      </Link>

      <section className="dashboard-card flex flex-wrap items-center gap-5 rounded-2xl p-5 sm:p-6">
        <UserAvatar user={profile} size="h-16 w-16 text-lg" />
        <div className="min-w-0 flex-1">
          <h1 className="custom-font text-2xl sm:text-3xl">{profile.full_name}</h1>
          <div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-sm">
            <a href={`tel:${profile.phone}`} className="inline-flex items-center gap-1 hover:underline">
              <FiPhone className="h-3.5 w-3.5" aria-hidden="true" />
              {profile.phone}
            </a>
            {profile.email && (
              <a href={`mailto:${profile.email}`} className="inline-flex items-center gap-1 break-all hover:underline">
                <FiMail className="h-3.5 w-3.5" aria-hidden="true" />
                {profile.email}
              </a>
            )}
          </div>
          <p className="showcase-muted mt-1 text-xs">
            Customer since {formatOrderDateTime(profile.date_joined)}
            {profile.created_via_checkout && " · account created at checkout"}
            {!profile.is_active && " · deactivated"}
          </p>
        </div>
      </section>

      <section aria-label="Order stats" className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="dashboard-card rounded-2xl p-5">
          <p className="showcase-muted text-sm">Orders</p>
          <p className="mt-1 text-2xl font-semibold">{stats.order_count}</p>
        </div>
        <div className="dashboard-card rounded-2xl p-5">
          <p className="showcase-muted text-sm">Total spent</p>
          <p className="mt-1 text-2xl font-semibold">{money(stats.total_spent)}</p>
          <p className="showcase-muted text-xs">Excludes cancelled, failed and returned orders</p>
        </div>
        <div className="dashboard-card rounded-2xl p-5">
          <p className="showcase-muted text-sm">Last order</p>
          <p className="mt-1 text-lg font-semibold">{stats.last_order_at ? formatOrderDateTime(stats.last_order_at) : "—"}</p>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
        <section className="dashboard-card rounded-2xl p-5 sm:p-6">
          <h2 className="custom-font text-lg font-bold">Recent Orders</h2>
          {profile.recent_orders.length === 0 ? (
            <p className="showcase-muted mt-3 text-sm">No orders yet.</p>
          ) : (
            <ul className="mt-3 flex flex-col divide-y text-sm">
              {profile.recent_orders.map((o) => (
                <li key={o.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div>
                    <Link href={`/dashboard/admin/orders/${o.id}`} className="font-medium hover:underline">
                      {o.number}
                    </Link>
                    <p className="showcase-muted text-xs">{formatOrderDateTime(o.created_at)}</p>
                  </div>
                  <span className="text-xs">{STATUS_LABEL[o.status] ?? o.status}</span>
                  <span className="font-semibold">{money(o.grand_total)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="flex flex-col gap-6">
          <section className="dashboard-card rounded-2xl p-5">
            <h2 className="custom-font text-lg font-bold">Tags</h2>
            <ul className="mt-3 flex flex-wrap gap-2">
              {tags.length === 0 && <li className="showcase-muted text-sm">No tags.</li>}
              {tags.map((name) => (
                <li key={name} className="product-card__chip inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium">
                  {name}
                  <button
                    type="button"
                    onClick={() => saveTags(tags.filter((t) => t !== name))}
                    disabled={busy}
                    aria-label={`Remove tag ${name}`}
                  >
                    <FiX className="h-3 w-3" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (tagInput.trim()) saveTags([...tags, tagInput.trim()]);
              }}
              className="mt-3 grid grid-cols-[minmax(0,1fr)_auto] gap-2"
            >
              <label htmlFor="cc-tag" className="sr-only">
                Add a tag
              </label>
              <input
                id="cc-tag"
                list="cc-tag-options"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                maxLength={40}
                placeholder="e.g. VIP"
                className="checkout-input w-full rounded-lg px-3 py-2 text-sm"
              />
              <datalist id="cc-tag-options">
                {suggestions.map((t) => (
                  <option key={t.id} value={t.name} />
                ))}
              </datalist>
              <button type="submit" disabled={busy || !tagInput.trim()} className="auth-btn auth-btn--outline rounded-full px-4 py-2 text-xs font-medium">
                Add
              </button>
            </form>
          </section>

          <section className="dashboard-card rounded-2xl p-5">
            <h2 className="custom-font text-lg font-bold">Care Notes</h2>
            <form onSubmit={addNote} className="mt-3 flex flex-col gap-2">
              <label htmlFor="cc-note" className="sr-only">
                Add a care note
              </label>
              <textarea
                id="cc-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                maxLength={2000}
                placeholder="e.g. Prefers evening calls. Sensitive skin."
                className="checkout-input w-full rounded-lg px-3 py-2 text-sm"
              />
              <button type="submit" disabled={busy} className="auth-btn auth-btn--primary w-fit rounded-full px-4 py-2 text-xs font-medium">
                Add Note
              </button>
            </form>
            <ul className="mt-4 flex flex-col gap-3">
              {profile.notes.map((n) => (
                <li key={n.id} className="flex items-start justify-between gap-2 text-sm">
                  <div className="min-w-0">
                    <p className="whitespace-pre-line">{n.text}</p>
                    <p className="showcase-muted text-xs">
                      {n.author?.full_name ?? "Staff"} · {formatOrderDateTime(n.created_at)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setPendingDelete(n)}
                    aria-label="Delete note"
                    className="icon-action icon-action--danger flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
                  >
                    <FiTrash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Note?"
        description="This care note will be removed."
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={busy}
        onConfirm={deleteNote}
        onCancel={() => !busy && setPendingDelete(null)}
      />
    </div>
  );
}
