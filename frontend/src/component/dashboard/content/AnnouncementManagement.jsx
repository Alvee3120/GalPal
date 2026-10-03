"use client";

import { useState } from "react";
import { FiEdit2, FiPlus, FiTrash2, FiVolume2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { formatOrderDateTime } from "@/lib/orderStatus";
import { contentFetch } from "@/lib/contentAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import Modal from "@/component/shared/Modal";

const INPUT = "checkout-input w-full rounded-lg px-3 py-2.5 text-sm";
const EMPTY = { text: "", link_url: "", starts_at: "", ends_at: "", sort_order: 0, is_active: true };

// <input type="datetime-local"> works in local time without a zone; the API takes ISO timestamps.
const toLocalInput = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
const fromLocalInput = (value) => (value ? new Date(value).toISOString() : null);

function AnnouncementForm({ initial, onSaved, onClose }) {
  const isEdit = Boolean(initial.id);
  const [form, setForm] = useState({ ...initial, starts_at: toLocalInput(initial.starts_at), ends_at: toLocalInput(initial.ends_at) });
  const [saving, setSaving] = useState(false);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    const body = {
      text: form.text.trim(),
      link_url: form.link_url.trim(),
      starts_at: fromLocalInput(form.starts_at),
      ends_at: fromLocalInput(form.ends_at),
      sort_order: Number(form.sort_order) || 0,
      is_active: form.is_active,
    };
    const res = isEdit ? await contentFetch(`announcements/${initial.id}`, { method: "PATCH", body }) : await contentFetch("announcements", { method: "POST", body });
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to save the announcement."));
    notify.success(isEdit ? "Announcement updated." : "Announcement added.");
    onSaved(res.data);
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-4">
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">Text</span>
        <input value={form.text} required maxLength={200} placeholder="e.g. Free delivery this weekend" onChange={(e) => set({ text: e.target.value })} className={INPUT} />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">Link (optional)</span>
        <input value={form.link_url} maxLength={300} placeholder="/shop or https://…" onChange={(e) => set({ link_url: e.target.value })} className={INPUT} />
      </label>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Starts</span>
          <input type="datetime-local" value={form.starts_at} onChange={(e) => set({ starts_at: e.target.value })} className={INPUT} />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Ends</span>
          <input type="datetime-local" value={form.ends_at} onChange={(e) => set({ ends_at: e.target.value })} className={INPUT} />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Sort order</span>
          <input type="number" min={0} value={form.sort_order} onChange={(e) => set({ sort_order: e.target.value })} className={INPUT} />
        </label>
      </div>
      <p className="showcase-muted -mt-2 text-xs">Leave the dates empty to show it until you turn it off.</p>
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.is_active} onChange={(e) => set({ is_active: e.target.checked })} />
        Active
      </label>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="auth-btn auth-btn--outline rounded-full px-5 py-2.5 text-sm font-medium">
          Cancel
        </button>
        <button type="submit" disabled={saving} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Announcement"}
        </button>
      </div>
    </form>
  );
}

function windowText(a) {
  if (!a.starts_at && !a.ends_at) return "Always";
  if (a.starts_at && a.ends_at) return `${formatOrderDateTime(a.starts_at)} → ${formatOrderDateTime(a.ends_at)}`;
  return a.starts_at ? `From ${formatOrderDateTime(a.starts_at)}` : `Until ${formatOrderDateTime(a.ends_at)}`;
}

// Admin → Announcements (Module 15): the bar above the storefront navbar. Live = active and inside its time window;
// several live ones take turns.
export default function AnnouncementManagement({ initial = [] }) {
  const [items, setItems] = useState(initial);
  const [editing, setEditing] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [busy, setBusy] = useState(false);
  const sorted = [...items].sort((a, b) => a.sort_order - b.sort_order || b.id - a.id);

  function onSaved(item) {
    setItems((list) => [...list.filter((x) => x.id !== item.id), item]);
    setEditing(null);
  }

  async function confirmDelete() {
    const target = pendingDelete;
    setBusy(true);
    const res = await contentFetch(`announcements/${target.id}`, { method: "DELETE" });
    setBusy(false);
    setPendingDelete(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the announcement."));
    setItems((list) => list.filter((x) => x.id !== target.id));
    notify.success("Announcement deleted.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Announcements</h1>
          <p className="showcase-muted mt-1 text-sm">The bar above the storefront navbar · {items.filter((a) => a.is_live).length} live</p>
        </div>
        <button type="button" onClick={() => setEditing({ ...EMPTY })} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          Add Announcement
        </button>
      </div>

      {sorted.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiVolume2 className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">No announcements</p>
          <p className="showcase-muted text-sm">The bar is hidden until you add one.</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {sorted.map((a) => (
            <li key={a.id} className="dashboard-card flex flex-wrap items-center gap-4 rounded-2xl p-5 text-sm">
              <div className="min-w-0 flex-1">
                <p className="font-semibold">{a.text}</p>
                <p className="showcase-muted text-xs">
                  {windowText(a)}
                  {a.link_url && ` · ${a.link_url}`} · #{a.sort_order}
                </p>
              </div>
              <span className="product-status-badge rounded-full px-2.5 py-0.5 text-xs font-medium" data-status={a.is_live ? "active" : a.is_active ? "draft" : "archived"}>
                {a.is_live ? "Live" : a.is_active ? "Scheduled / ended" : "Off"}
              </span>
              <div className="flex items-center gap-1.5">
                <button type="button" onClick={() => setEditing(a)} aria-label="Edit announcement" title="Edit" className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                  <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                </button>
                <button type="button" onClick={() => setPendingDelete(a)} aria-label="Delete announcement" title="Delete" className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full">
                  <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal open={Boolean(editing)} title={editing?.id ? "Edit Announcement" : "Add Announcement"} onClose={() => setEditing(null)} wide>
        {editing && <AnnouncementForm key={editing.id ?? "new"} initial={editing} onSaved={onSaved} onClose={() => setEditing(null)} />}
      </Modal>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Announcement?"
        description="It will disappear from the storefront bar."
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={busy}
        onConfirm={confirmDelete}
        onCancel={() => !busy && setPendingDelete(null)}
      />
    </div>
  );
}
