"use client";

import { useState } from "react";
import { FiEdit2, FiExternalLink, FiFileText, FiPlus, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { formatOrderDateTime } from "@/lib/orderStatus";
import { contentFetch, pagePath, slugify } from "@/lib/contentAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import Modal from "@/component/shared/Modal";
import RichText from "@/component/content/RichText";

const INPUT = "checkout-input w-full rounded-lg px-3 py-2.5 text-sm";
const EMPTY = { title: "", slug: "", content: "", meta_title: "", meta_description: "", is_active: true };

const FORMAT_HELP = "## Heading · ### Sub-heading · - bullet · 1. numbered · **bold** · [link text](/shop) · blank line = new paragraph";

function PageEditor({ initial, standardTitles, onSaved, onClose }) {
  const isEdit = Boolean(initial?.id);
  const [form, setForm] = useState(initial ?? EMPTY);
  const [slugTouched, setSlugTouched] = useState(isEdit);
  const [tab, setTab] = useState("write");
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});
  const slugLocked = isEdit && initial.is_standard;
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    const body = {
      title: form.title.trim(),
      slug: form.slug.trim(),
      content: form.content,
      meta_title: form.meta_title.trim(),
      meta_description: form.meta_description.trim(),
      is_active: form.is_active,
    };
    const res = isEdit ? await contentFetch(`pages/${initial.id}`, { method: "PATCH", body }) : await contentFetch("pages", { method: "POST", body });
    setSaving(false);
    if (!res.ok) {
      setErrors(res.data?.error?.details ?? {});
      return notify.error(errorText(res, "Unable to save the page."));
    }
    notify.success(isEdit ? "Page updated." : "Page created.");
    onSaved(res.data);
  }

  const fieldError = (name) => {
    const msg = errors?.[name];
    return msg ? <p className="mt-1 text-xs text-[color:var(--color-danger)]">{Array.isArray(msg) ? msg[0]?.message ?? msg[0] : String(msg)}</p> : null;
  };

  return (
    <form onSubmit={save} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Title</span>
          <input
            value={form.title}
            required
            maxLength={200}
            onChange={(e) => set({ title: e.target.value, ...(slugTouched ? {} : { slug: slugify(e.target.value) }) })}
            className={INPUT}
          />
          {fieldError("title")}
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Slug</span>
          <input
            value={form.slug}
            required
            maxLength={120}
            disabled={slugLocked}
            list="standard-slugs"
            onChange={(e) => {
              setSlugTouched(true);
              set({ slug: slugify(e.target.value) || e.target.value.toLowerCase() });
            }}
            className={INPUT}
          />
          <datalist id="standard-slugs">
            {Object.entries(standardTitles).map(([slug, title]) => (
              <option key={slug} value={slug}>
                {title}
              </option>
            ))}
          </datalist>
          <span className="showcase-muted text-xs">
            {slugLocked ? "Standard page: the slug is fixed." : "Shown at"} {form.slug ? pagePath(form.slug) : "/pages/…"}
          </span>
          {fieldError("slug")}
        </label>
      </div>

      <div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium">Content</span>
          <div className="flex gap-1 text-xs" role="tablist">
            {["write", "preview"].map((t) => (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
                className={`rounded-full px-3 py-1 font-medium ${tab === t ? "auth-btn auth-btn--primary" : "auth-btn auth-btn--outline"}`}
              >
                {t === "write" ? "Write" : "Preview"}
              </button>
            ))}
          </div>
        </div>
        {tab === "write" ? (
          <textarea
            value={form.content}
            required
            rows={16}
            maxLength={60000}
            onChange={(e) => set({ content: e.target.value })}
            className={`${INPUT} mt-2 font-mono`}
            aria-describedby="content-format"
          />
        ) : (
          <div className="content-preview legal-page mt-2 rounded-lg">
            {form.content.trim() ? <RichText text={form.content} sectioned /> : <p className="showcase-muted">Nothing to preview yet.</p>}
          </div>
        )}
        <p id="content-format" className="showcase-muted mt-1 text-xs">
          {FORMAT_HELP}
        </p>
        {fieldError("content")}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">SEO title</span>
          <input value={form.meta_title} maxLength={200} onChange={(e) => set({ meta_title: e.target.value })} placeholder={form.title} className={INPUT} />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">SEO description</span>
          <input value={form.meta_description} maxLength={300} onChange={(e) => set({ meta_description: e.target.value })} className={INPUT} />
        </label>
      </div>

      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.is_active} onChange={(e) => set({ is_active: e.target.checked })} />
        Active (shown on the storefront)
      </label>

      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="auth-btn auth-btn--outline rounded-full px-5 py-2.5 text-sm font-medium">
          Cancel
        </button>
        <button type="submit" disabled={saving} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Create Page"}
        </button>
      </div>
    </form>
  );
}

// Admin → Content Pages (Module 15): the storefront's About / policy pages and any custom page. A standard page
// (about, privacy-policy, terms, return-and-cancellation-policy, shipping-policy) replaces that route's built-in text
// while it is active; deleting or deactivating it brings the built-in text back.
export default function ContentPages({ initial = [], standardTitles = {} }) {
  const [pages, setPages] = useState(initial);
  const [editing, setEditing] = useState(null); // page object, a new-page template, or null
  const [pendingDelete, setPendingDelete] = useState(null);
  const [busy, setBusy] = useState(false);
  const missing = Object.entries(standardTitles).filter(([slug]) => !pages.some((p) => p.slug === slug));

  function onSaved(page) {
    setPages((list) => {
      const rest = list.filter((p) => p.id !== page.id);
      return [...rest, page].sort((a, b) => a.title.localeCompare(b.title));
    });
    setEditing(null);
  }

  async function confirmDelete() {
    const target = pendingDelete;
    setBusy(true);
    const res = await contentFetch(`pages/${target.id}`, { method: "DELETE" });
    setBusy(false);
    setPendingDelete(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the page."));
    setPages((list) => list.filter((p) => p.id !== target.id));
    notify.success("Page deleted.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Content Pages</h1>
          <p className="showcase-muted mt-1 text-sm">About, policies and other storefront pages · {pages.length}</p>
        </div>
        <button type="button" onClick={() => setEditing({ ...EMPTY })} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          New Page
        </button>
      </div>

      {missing.length > 0 && (
        <section className="dashboard-card rounded-2xl p-5">
          <h2 className="custom-font text-lg font-bold">Standard pages using built-in text</h2>
          <p className="showcase-muted mt-1 text-xs">Create one to write your own version; the storefront switches to it right away.</p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {missing.map(([slug, title]) => (
              <li key={slug}>
                <button
                  type="button"
                  onClick={() => setEditing({ ...EMPTY, title, slug })}
                  className="auth-btn auth-btn--outline inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-medium"
                >
                  <FiPlus className="h-3.5 w-3.5" aria-hidden="true" />
                  {title}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {pages.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiFileText className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">No content pages yet</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {pages.map((page) => (
            <li key={page.id} className="dashboard-card flex flex-wrap items-center gap-4 rounded-2xl p-5 text-sm">
              <div className="min-w-0 flex-1">
                <p className="font-semibold">
                  {page.title}
                  {page.is_standard && <span className="showcase-muted ml-2 text-xs font-normal">Standard</span>}
                </p>
                <p className="showcase-muted text-xs">
                  {pagePath(page.slug)} · updated {formatOrderDateTime(page.updated_at)}
                  {page.updated_by && ` by ${page.updated_by}`}
                </p>
              </div>
              <span className="product-status-badge rounded-full px-2.5 py-0.5 text-xs font-medium" data-status={page.is_active ? "active" : "draft"}>
                {page.is_active ? "Active" : "Hidden"}
              </span>
              <div className="flex items-center gap-1.5">
                {page.is_active && (
                  <a href={pagePath(page.slug)} target="_blank" rel="noopener noreferrer" title="View on the site" aria-label={`View ${page.title}`} className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                    <FiExternalLink className="h-4 w-4" aria-hidden="true" />
                  </a>
                )}
                <button type="button" onClick={() => setEditing(page)} title="Edit" aria-label={`Edit ${page.title}`} className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                  <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                </button>
                <button type="button" onClick={() => setPendingDelete(page)} title="Delete" aria-label={`Delete ${page.title}`} className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full">
                  <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal open={Boolean(editing)} title={editing?.id ? "Edit Page" : "New Page"} onClose={() => setEditing(null)} xl>
        {editing && <PageEditor key={editing.id ?? editing.slug ?? "new"} initial={editing.id ? editing : { ...EMPTY, ...editing }} standardTitles={standardTitles} onSaved={onSaved} onClose={() => setEditing(null)} />}
      </Modal>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Page?"
        description={pendingDelete?.is_standard ? "The storefront will go back to its built-in text for this page." : "This page will be removed from the site."}
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={busy}
        onConfirm={confirmDelete}
        onCancel={() => !busy && setPendingDelete(null)}
      />
    </div>
  );
}
