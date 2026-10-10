"use client";

import { useCallback, useEffect, useState } from "react";
import { FiEdit2, FiLayout, FiPlus, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { catalogFetch, errorText } from "@/lib/productAdmin";
import { flattenCategoryTree } from "@/lib/categoryAdmin";
import { contentFetch } from "@/lib/contentAdmin";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import Modal from "@/component/shared/Modal";
import SearchPicker from "../SearchPicker";

const INPUT = "checkout-input w-full rounded-lg px-3 py-2.5 text-sm";
// Mirrors apps.content.models.SectionPosition.
const POSITIONS = [
  { value: "before_video", label: "Before Skincare Video" },
  { value: "after_video", label: "After Skincare Video" },
];
const POSITION_LABEL = Object.fromEntries(POSITIONS.map((p) => [p.value, p.label]));
// Mirrors apps.content.models.SectionSource / FLAG_SOURCES: a category, or one of the product flags from Product Management.
const SOURCES = [
  { value: "category", label: "Category", title: "" },
  { value: "featured", label: "Trending (Is Featured)", title: "Trending Products" },
  { value: "new_arrival", label: "New Arrivals (Is New Arrival)", title: "New Arrivals" },
  { value: "bestseller", label: "Bestsellers (Is Bestseller)", title: "Bestsellers" },
];
const SOURCE = Object.fromEntries(SOURCES.map((s) => [s.value, s]));
const EMPTY = { source: "category", category: null, title: "", position: "before_video", sort_order: "0", product_limit: "8", rows: "1", is_active: true };
const byOrder = (a, b) => a.position.localeCompare(b.position) * -1 || a.sort_order - b.sort_order || a.id - b.id; // before_video first

// Picker items: every category with its place in the tree, inactive ones marked (they won't show on the homepage).
function categoryItems(tree) {
  const trail = [];
  return flattenCategoryTree(tree).map((c) => {
    trail[c.depth] = c.name;
    trail.length = c.depth + 1;
    const path = trail.slice(0, -1).join(" › ");
    return { id: c.id, label: c.name, hint: [path || "Top level", c.is_active === false ? "Inactive" : ""].filter(Boolean).join(" · ") };
  });
}

function SectionForm({ initial, categories, onSaved, onClose }) {
  const isEdit = Boolean(initial.id);
  const [v, setV] = useState(initial);
  const [saving, setSaving] = useState(false);
  const set = (name) => (value) => setV((s) => ({ ...s, [name]: value }));

  const searchCategories = useCallback(
    async (query) => {
      const q = query.toLowerCase();
      return categories.filter((c) => !q || c.label.toLowerCase().includes(q)).slice(0, 50);
    },
    [categories],
  );

  const isCategory = v.source === "category";

  async function save(e) {
    e.preventDefault();
    if (isCategory && !v.category) return notify.error("Choose a category.");
    const limit = Number(v.product_limit);
    const rows = Number(v.rows);
    if (!Number.isInteger(limit) || limit < 1 || limit > 48) return notify.error("Product limit must be a whole number from 1 to 48.");
    if (!Number.isInteger(rows) || rows < 1 || rows > 4) return notify.error("Rows must be a whole number from 1 to 4.");
    setSaving(true);
    const body = {
      source: v.source,
      category_id: isCategory ? v.category.id : null,
      title: isCategory ? "" : v.title.trim() || SOURCE[v.source].title,
      position: v.position,
      sort_order: Number(v.sort_order) || 0,
      product_limit: limit,
      rows,
      is_active: v.is_active,
    };
    const res = isEdit ? await contentFetch(`category-sections/${initial.id}`, { method: "PATCH", body }) : await contentFetch("category-sections", { method: "POST", body });
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to save the section."));
    notify.success(isEdit ? "Section updated." : "Section added.");
    onSaved(res.data);
  }

  return (
    <form onSubmit={save} noValidate className="flex flex-col gap-4">
      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">Products from</span>
        <select
          value={v.source}
          disabled={isEdit}
          onChange={(e) => setV((s) => ({ ...s, source: e.target.value, title: s.title || SOURCE[e.target.value].title }))}
          className={INPUT}
        >
          {SOURCES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        {isEdit && <span className="showcase-muted text-xs">To use a different source, add a new section.</span>}
      </label>
      {isCategory ? (
        <>
          <SearchPicker
            id="hs-category"
            label="Category"
            placeholder="Search categories..."
            search={searchCategories}
            value={v.category}
            onChange={set("category")}
            required
          />
          <p className="showcase-muted -mt-2 text-xs">The section&apos;s title is the category&apos;s name; its products include its sub-categories&apos;.</p>
        </>
      ) : (
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Section title</span>
          <input value={v.title} maxLength={80} placeholder={SOURCE[v.source].title} onChange={(e) => set("title")(e.target.value)} className={INPUT} />
          <span className="showcase-muted text-xs">
            Shows published products with the {SOURCE[v.source].label.match(/\((.*)\)/)?.[1]} box ticked in Product Management. The title only
            changes the heading.
          </span>
        </label>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Position</span>
          <select value={v.position} onChange={(e) => set("position")(e.target.value)} className={INPUT}>
            {POSITIONS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Order</span>
          <input type="number" min={0} step={1} value={v.sort_order} onChange={(e) => set("sort_order")(e.target.value)} className={INPUT} />
          <span className="showcase-muted text-xs">Lower shows first, within its position.</span>
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Product limit</span>
          <input type="number" min={1} max={48} step={1} value={v.product_limit} onChange={(e) => set("product_limit")(e.target.value)} className={INPUT} />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm font-medium">Rows</span>
          <input type="number" min={1} max={4} step={1} value={v.rows} onChange={(e) => set("rows")(e.target.value)} className={INPUT} />
        </label>
      </div>
      <label className="inline-flex items-center gap-2 text-sm">
        <input type="checkbox" checked={v.is_active} onChange={(e) => set("is_active")(e.target.checked)} className="form-check h-4 w-4" />
        Active (shown on the homepage)
      </label>
      <div className="flex justify-end gap-2">
        <button type="button" onClick={onClose} className="auth-btn auth-btn--outline rounded-full px-5 py-2.5 text-sm font-medium">
          Cancel
        </button>
        <button type="submit" disabled={saving} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Section"}
        </button>
      </div>
    </form>
  );
}

// Admin → Homepage Sections: the product sections around the homepage's skincare video section (apps.content
// HomepageCategorySection, IsAdmin): a category (titled with the category's own name) or Trending / New Arrivals /
// Bestsellers (products with that flag ticked in Product Management, with an editable title). Each one is the
// storefront's shared product showcase; the homepage refreshes as soon as a change is saved.
export default function HomepageSectionsManagement({ initial = [] }) {
  const [sections, setSections] = useState([...initial].sort(byOrder));
  const [categories, setCategories] = useState([]);
  const [editing, setEditing] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    catalogFetch("categories/tree").then((res) => {
      if (cancelled) return;
      if (!res.ok) notify.error("Categories couldn't be loaded. Please refresh.");
      setCategories(res.ok ? categoryItems(res.data) : []);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  function onSaved(section) {
    setSections((list) => [...list.filter((s) => s.id !== section.id), section].sort(byOrder));
    setEditing(null);
  }

  async function toggle(section) {
    const res = await contentFetch(`category-sections/${section.id}`, { method: "PATCH", body: { is_active: !section.is_active } });
    if (!res.ok) return notify.error(errorText(res, "Unable to update the section."));
    onSaved(res.data);
  }

  async function confirmDelete() {
    const target = pendingDelete;
    setBusy(true);
    const res = await contentFetch(`category-sections/${target.id}`, { method: "DELETE" });
    setBusy(false);
    setPendingDelete(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to remove the section."));
    setSections((list) => list.filter((s) => s.id !== target.id));
    notify.success("Section removed.");
  }

  const toForm = (s) => ({
    id: s.id,
    source: s.source,
    title: s.title ?? "",
    category: s.category ? { id: s.category.id, label: s.category.name } : null,
    position: s.position,
    sort_order: String(s.sort_order),
    product_limit: String(s.product_limit),
    rows: String(s.rows),
    is_active: s.is_active,
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Homepage Sections</h1>
          <p className="showcase-muted mt-1 text-sm">
            Product sections before and after the skincare video — categories, Trending, New Arrivals, Bestsellers · {sections.length}
          </p>
        </div>
        <button type="button" onClick={() => setEditing({ ...EMPTY })} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
          <FiPlus className="h-4 w-4" aria-hidden="true" />
          Add Section
        </button>
      </div>

      {sections.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <FiLayout className="showcase-muted h-8 w-8" aria-hidden="true" />
          <p className="custom-font text-xl">No homepage category sections</p>
          <p className="showcase-muted text-sm">Add one to show a category&apos;s products on the homepage.</p>
        </div>
      ) : (
        <>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[860px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Section</th>
                  <th scope="col" className="px-4 py-3 font-medium">Products From</th>
                  <th scope="col" className="px-4 py-3 font-medium">Position</th>
                  <th scope="col" className="px-4 py-3 font-medium">Order</th>
                  <th scope="col" className="px-4 py-3 font-medium">Products</th>
                  <th scope="col" className="px-4 py-3 font-medium">Rows</th>
                  <th scope="col" className="px-4 py-3 font-medium">Status</th>
                  <th scope="col" className="px-4 py-3 font-medium">Edit</th>
                  <th scope="col" className="px-4 py-3 font-medium">Delete</th>
                </tr>
              </thead>
              <tbody>
                {sections.map((s) => (
                  <tr key={s.id}>
                    <td className="px-4 py-3 font-semibold">
                      {s.display_title}
                      {s.category && !s.category.is_active && (
                        <span className="showcase-muted block text-xs font-normal">Category inactive — hidden on the homepage</span>
                      )}
                    </td>
                    <td className="px-4 py-3">{s.source === "category" ? "Category" : SOURCE[s.source]?.label ?? s.source}</td>
                    <td className="px-4 py-3">{POSITION_LABEL[s.position] ?? s.position}</td>
                    <td className="px-4 py-3 tabular-nums">{s.sort_order}</td>
                    <td className="px-4 py-3 tabular-nums">{s.product_limit}</td>
                    <td className="px-4 py-3 tabular-nums">{s.rows}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => toggle(s)}
                        className="coupon-status rounded-full px-2.5 py-1 text-xs font-medium"
                        data-status={s.is_active ? "active" : "inactive"}
                        title={s.is_active ? "Click to hide" : "Click to show"}
                      >
                        {s.is_active ? "Active" : "Inactive"}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <button type="button" onClick={() => setEditing(toForm(s))} title="Edit section" aria-label={`Edit ${s.display_title} section`} className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                        <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <button type="button" onClick={() => setPendingDelete(s)} title="Remove section" aria-label={`Remove ${s.display_title} section`} className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full">
                        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 md:hidden">
            {sections.map((s) => (
              <li key={s.id} className="dashboard-card flex flex-col gap-2 rounded-2xl p-4 text-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold">{s.display_title}</p>
                    <p className="showcase-muted text-xs">
                      {SOURCE[s.source]?.label ?? s.source} · {POSITION_LABEL[s.position]} · order {s.sort_order} · {s.product_limit} products · {s.rows} row{s.rows === 1 ? "" : "s"}
                    </p>
                  </div>
                  <button type="button" onClick={() => toggle(s)} className="coupon-status rounded-full px-2.5 py-1 text-xs font-medium" data-status={s.is_active ? "active" : "inactive"}>
                    {s.is_active ? "Active" : "Inactive"}
                  </button>
                </div>
                <div className="flex justify-end gap-1.5">
                  <button type="button" onClick={() => setEditing(toForm(s))} aria-label={`Edit ${s.display_title} section`} className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                    <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button type="button" onClick={() => setPendingDelete(s)} aria-label={`Remove ${s.display_title} section`} className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full">
                    <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      <Modal open={Boolean(editing)} title={editing?.id ? "Edit Section" : "Add Section"} onClose={() => setEditing(null)} wide>
        {editing && <SectionForm key={editing.id ?? "new"} initial={editing} categories={categories} onSaved={onSaved} onClose={() => setEditing(null)} />}
      </Modal>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Remove Section?"
        description={`The ${pendingDelete?.display_title ?? ""} section will be removed from the homepage. Its products aren't affected.`}
        confirmLabel="Remove"
        busyLabel="Removing..."
        busy={busy}
        onConfirm={confirmDelete}
        onCancel={() => !busy && setPendingDelete(null)}
      />
    </div>
  );
}
