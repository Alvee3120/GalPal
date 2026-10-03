"use client";

import { useMemo, useState } from "react";
import { FiEdit2, FiHelpCircle, FiPlus, FiSearch, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { contentFetch } from "@/lib/contentAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import Modal from "@/component/shared/Modal";

const INPUT = "checkout-input w-full rounded-lg px-3 py-2.5 text-sm";
const EMPTY = { category: "", question: "", answer: "", sort_order: 0, is_active: true };
const byOrder = (a, b) => a.category.localeCompare(b.category) || a.sort_order - b.sort_order || a.id - b.id;

function FaqForm({ initial, categories, onSaved, onClose }) {
  const isEdit = Boolean(initial.id);
  const [form, setForm] = useState(initial);
  const [saving, setSaving] = useState(false);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    const body = { category: form.category.trim(), question: form.question.trim(), answer: form.answer.trim(), sort_order: Number(form.sort_order) || 0, is_active: form.is_active };
    const res = isEdit ? await contentFetch(`faqs/${initial.id}`, { method: "PATCH", body }) : await contentFetch("faqs", { method: "POST", body });
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to save the question."));
    notify.success(isEdit ? "Question updated." : "Question added.");
    onSaved(res.data);
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Category</span>
          <input value={form.category} maxLength={60} list="faq-categories" placeholder="e.g. Orders, Delivery, Payment" onChange={(e) => set({ category: e.target.value })} className={INPUT} />
          <datalist id="faq-categories">
            {categories.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Sort order</span>
          <input type="number" min={0} value={form.sort_order} onChange={(e) => set({ sort_order: e.target.value })} className={INPUT} />
        </label>
      </div>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">Question</span>
        <input value={form.question} required maxLength={300} onChange={(e) => set({ question: e.target.value })} className={INPUT} />
      </label>
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">Answer</span>
        <textarea value={form.answer} required rows={6} maxLength={5000} onChange={(e) => set({ answer: e.target.value })} className={INPUT} />
        <span className="showcase-muted text-xs">Supports - bullets, **bold** and [links](/shop).</span>
      </label>
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.is_active} onChange={(e) => set({ is_active: e.target.checked })} />
        Show on the FAQ page
      </label>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="auth-btn auth-btn--outline rounded-full px-5 py-2.5 text-sm font-medium">
          Cancel
        </button>
        <button type="submit" disabled={saving} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Question"}
        </button>
      </div>
    </form>
  );
}

// Admin → FAQs (Module 15): the questions on the storefront /faq page, grouped by category, lower sort order first.
export default function FaqManagement({ initial = [] }) {
  const [faqs, setFaqs] = useState([...initial].sort(byOrder));
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [busy, setBusy] = useState(false);
  const categories = useMemo(() => [...new Set(faqs.map((f) => f.category).filter(Boolean))], [faqs]);
  const q = search.trim().toLowerCase();
  const shown = q ? faqs.filter((f) => `${f.question} ${f.answer} ${f.category}`.toLowerCase().includes(q)) : faqs;

  function onSaved(faq) {
    setFaqs((list) => [...list.filter((f) => f.id !== faq.id), faq].sort(byOrder));
    setEditing(null);
  }

  async function toggle(faq) {
    const res = await contentFetch(`faqs/${faq.id}`, { method: "PATCH", body: { is_active: !faq.is_active } });
    if (!res.ok) return notify.error(errorText(res, "Unable to update the question."));
    onSaved(res.data);
  }

  async function confirmDelete() {
    const target = pendingDelete;
    setBusy(true);
    const res = await contentFetch(`faqs/${target.id}`, { method: "DELETE" });
    setBusy(false);
    setPendingDelete(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the question."));
    setFaqs((list) => list.filter((f) => f.id !== target.id));
    notify.success("Question deleted.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">FAQs</h1>
          <p className="showcase-muted mt-1 text-sm">Questions on the storefront FAQ page · {faqs.length}</p>
        </div>
        <button type="button" onClick={() => setEditing({ ...EMPTY })} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          Add Question
        </button>
      </div>

      <div className="relative">
        <label htmlFor="faq-search" className="sr-only">
          Search questions
        </label>
        <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
        <input id="faq-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search questions..." className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm" />
      </div>

      {shown.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiHelpCircle className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">{faqs.length ? "No matching questions" : "No questions yet"}</p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {shown.map((faq) => (
            <li key={faq.id} className="dashboard-card flex flex-wrap items-start gap-4 rounded-2xl p-5 text-sm">
              <div className="min-w-0 flex-1">
                <p className="showcase-muted text-xs">
                  {faq.category || "General"} · #{faq.sort_order}
                </p>
                <p className="mt-0.5 font-semibold">{faq.question}</p>
                <p className="showcase-muted mt-1 line-clamp-2 whitespace-pre-line">{faq.answer}</p>
              </div>
              <button
                type="button"
                onClick={() => toggle(faq)}
                className="product-status-badge rounded-full px-2.5 py-0.5 text-xs font-medium"
                data-status={faq.is_active ? "active" : "draft"}
                title={faq.is_active ? "Click to hide" : "Click to show"}
              >
                {faq.is_active ? "Shown" : "Hidden"}
              </button>
              <div className="flex items-center gap-1.5">
                <button type="button" onClick={() => setEditing(faq)} aria-label="Edit question" title="Edit" className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                  <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                </button>
                <button type="button" onClick={() => setPendingDelete(faq)} aria-label="Delete question" title="Delete" className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full">
                  <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Modal open={Boolean(editing)} title={editing?.id ? "Edit Question" : "Add Question"} onClose={() => setEditing(null)} wide>
        {editing && <FaqForm key={editing.id ?? "new"} initial={editing} categories={categories} onSaved={onSaved} onClose={() => setEditing(null)} />}
      </Modal>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Question?"
        description="It will be removed from the FAQ page."
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={busy}
        onConfirm={confirmDelete}
        onCancel={() => !busy && setPendingDelete(null)}
      />
    </div>
  );
}
