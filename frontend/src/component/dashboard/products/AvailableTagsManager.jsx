"use client";

import { useState } from "react";
import { FiEdit2, FiTrash2 } from "react-icons/fi";
import Modal from "@/component/shared/Modal";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import { notify } from "@/lib/notify";
import { catalogFetch, errorText } from "@/lib/productAdmin";

// "Available Tags" manager shown under the product's Tags field: every existing tag as a chip with Edit/Delete,
// over the EXISTING /admin/tags/ API (the same list ProductForm already loads; PATCH/DELETE are the endpoints the
// backend now lets Admin and CCE use). Renames and deletions are reported upward so the product's chosen tags and
// the picker above stay in sync — no tag is ever deleted silently, and the confirmation names how many products use it.
export default function AvailableTagsManager({ tags = [], loading, selectedIds = [], onTagsChange, onChange }) {
  const [editing, setEditing] = useState(null); // the tag being renamed
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);

  function openEdit(tag) {
    setEditing(tag);
    setName(tag.name);
  }

  async function saveTag(e) {
    e?.preventDefault(); // Enter must not submit the product form
    const trimmed = name.trim();
    if (!editing || saving) return;
    if (!trimmed) return notify.error("Tag name is required.");
    if (tags.some((t) => t.id !== editing.id && t.name.trim().toLowerCase() === trimmed.toLowerCase())) {
      return notify.error("A tag with this name already exists.");
    }
    setSaving(true);
    const res = await catalogFetch(`tags/${editing.id}`, { method: "PATCH", body: { name: trimmed } });
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to update the tag. Please try again."));
    onTagsChange(tags.map((t) => (t.id === editing.id ? { ...t, ...res.data } : t)));
    notify.success(`Tag "${res.data.name}" updated.`);
    setEditing(null);
  }

  async function confirmDelete() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    const res = await catalogFetch(`tags/${pendingDelete.id}`, { method: "DELETE" });
    setDeleting(false);
    if (!res.ok) {
      setPendingDelete(null);
      return notify.error(errorText(res, "Unable to delete the tag. Please try again."));
    }
    // Drop it from the available list, and from this product's chosen tags if it was selected.
    onTagsChange(tags.filter((t) => t.id !== pendingDelete.id));
    if (selectedIds.includes(pendingDelete.id)) onChange(selectedIds.filter((id) => id !== pendingDelete.id));
    notify.success(`Tag "${pendingDelete.name}" deleted.`);
    setPendingDelete(null);
  }

  const usage = Number(pendingDelete?.product_count ?? 0);

  return (
    <div className="available-tags mt-4 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium">Available Tags</h3>
        {!loading && tags.length > 0 && <span className="showcase-muted text-xs">{tags.length} total</span>}
      </div>

      {loading ? (
        <p className="showcase-muted mt-2 text-xs">Loading tags...</p>
      ) : tags.length === 0 ? (
        <p className="showcase-muted mt-2 text-xs">No tags yet. Use &quot;Add Tag&quot; above to create one.</p>
      ) : (
        <ul className="mt-3 flex flex-wrap gap-2">
          {tags.map((tag) => (
            <li key={tag.id} className="available-tags__chip flex items-center gap-1 rounded-full py-1 pl-3 pr-1.5 text-sm">
              <span className="max-w-48 truncate" title={tag.name}>
                {tag.name}
              </span>
              <button
                type="button"
                onClick={() => openEdit(tag)}
                title="Edit tag"
                aria-label={`Edit tag ${tag.name}`}
                className="icon-action flex h-7 w-7 items-center justify-center rounded-full"
              >
                <FiEdit2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => setPendingDelete(tag)}
                title="Delete tag"
                aria-label={`Delete tag ${tag.name}`}
                className="icon-action icon-action--danger flex h-7 w-7 items-center justify-center rounded-full"
              >
                <FiTrash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      <Modal open={Boolean(editing)} title="Edit Tag" onClose={() => !saving && setEditing(null)}>
        {/* Not a nested <form>: this dialog renders inside the product form, and forms can't nest. */}
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="edit-tag-name" className="text-sm font-medium">
              Tag Name
            </label>
            <input
              id="edit-tag-name"
              type="text"
              maxLength={60}
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && saveTag(e)}
              className="checkout-input rounded-lg px-3 py-2.5 text-sm"
            />
          </div>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setEditing(null)} disabled={saving} className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
              Cancel
            </button>
            <button
              type="button"
              onClick={saveTag}
              disabled={saving || !name.trim()}
              className="auth-btn auth-btn--primary rounded-full px-5 py-2 text-sm font-medium"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Tag?"
        description={
          pendingDelete
            ? usage > 0
              ? `"${pendingDelete.name}" is used by ${usage} product${usage === 1 ? "" : "s"}. Deleting it removes the tag from those products — the products themselves are kept. This can't be undone.`
              : `Are you sure you want to delete "${pendingDelete.name}"? This can't be undone.`
            : ""
        }
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}
