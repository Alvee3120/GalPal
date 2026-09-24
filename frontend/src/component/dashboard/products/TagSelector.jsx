"use client";

import { useState } from "react";
import { FiChevronLeft, FiChevronRight, FiPlus, FiSearch } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { catalogFetch, errorText } from "@/lib/productAdmin";
import Modal from "@/component/shared/Modal";

function TagList({ id, title, tags, filter, onFilter, highlighted, onToggle, onMove, emptyText }) {
  const shown = tags.filter((t) => t.name.toLowerCase().includes(filter.trim().toLowerCase()));
  return (
    <div className="tag-pane flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl">
      <p id={`${id}-label`} className="tag-pane__head px-3 py-2.5 text-sm font-medium">
        {title} <span className="showcase-muted font-normal">({tags.length})</span>
      </p>
      <div className="relative px-3 pb-2">
        <FiSearch className="showcase-muted pointer-events-none absolute left-5.5 top-[calc(50%-4px)] h-3.5 w-3.5 -translate-y-1/2" aria-hidden="true" />
        <input
          type="search"
          value={filter}
          onChange={(e) => onFilter(e.target.value)}
          placeholder="Search tags..."
          aria-label={`Filter ${title.toLowerCase()}`}
          className="checkout-input rounded-lg py-2 pl-8 pr-2 text-sm"
        />
      </div>
      <ul role="listbox" aria-multiselectable="true" aria-labelledby={`${id}-label`} className="tag-pane__list h-48 overflow-y-auto p-1.5">
        {shown.length === 0 && <li className="showcase-muted px-2 py-1.5 text-xs">{filter.trim() ? "No matching tags." : emptyText}</li>}
        {shown.map((tag) => (
          <li key={tag.id} role="presentation">
            <button
              type="button"
              role="option"
              aria-selected={highlighted.has(tag.id)}
              onClick={() => onToggle(tag.id)}
              onDoubleClick={() => onMove([tag.id])}
              className="tag-pane__item w-full rounded-md px-2.5 py-1.5 text-left text-sm"
            >
              {tag.name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Tags field (the dual-list pattern from Django admin's filter_horizontal, restyled for the dashboard): pick tags on
// the left, move them across with the arrow buttons (or double-click), filter either side, and create a new tag
// in place. `allTags` comes from the EXISTING /admin/tags/ API; "+ Add Tag" POSTs there too, and the backend
// rejects a duplicate name (apps.catalog.serializers.AdminTagSerializer / _UniqueNameMixin).
export default function TagSelector({ allTags, onTagsChange, selectedIds, onChange }) {
  const [availableFilter, setAvailableFilter] = useState("");
  const [chosenFilter, setChosenFilter] = useState("");
  const [availableHighlight, setAvailableHighlight] = useState(new Set());
  const [chosenHighlight, setChosenHighlight] = useState(new Set());
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [saving, setSaving] = useState(false);

  const selected = new Set(selectedIds);
  const byName = (a, b) => a.name.localeCompare(b.name);
  const available = allTags.filter((t) => !selected.has(t.id)).sort(byName);
  const chosen = allTags.filter((t) => selected.has(t.id)).sort(byName);

  const toggle = (setter) => (tagId) =>
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(tagId)) next.delete(tagId);
      else next.add(tagId);
      return next;
    });

  function choose(ids) {
    if (!ids.length) return;
    onChange([...selectedIds, ...ids.filter((i) => !selected.has(i))]);
    setAvailableHighlight(new Set());
  }

  function remove(ids) {
    if (!ids.length) return;
    const drop = new Set(ids);
    onChange(selectedIds.filter((i) => !drop.has(i)));
    setChosenHighlight(new Set());
  }

  async function createTag(e) {
    e.preventDefault();
    const name = newName.trim();
    if (!name || saving) return;
    setSaving(true);
    const res = await catalogFetch("tags", { method: "POST", body: { name } });
    setSaving(false);
    if (!res.ok) {
      notify.error(errorText(res, "Unable to add the tag. Please try again."));
      return;
    }
    onTagsChange([...allTags, res.data]);
    onChange([...selectedIds, res.data.id]); // a tag created from this form is meant for this product
    notify.success(`Tag "${res.data.name}" added.`);
    setNewName("");
    setAdding(false);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-stretch">
        <TagList
          id="tags-available"
          title="Available tags"
          tags={available}
          filter={availableFilter}
          onFilter={setAvailableFilter}
          highlighted={availableHighlight}
          onToggle={toggle(setAvailableHighlight)}
          onMove={choose}
          emptyText="Every tag is chosen."
        />
        <div className="flex items-center justify-center gap-2 sm:flex-col">
          <button
            type="button"
            onClick={() => choose([...availableHighlight])}
            disabled={availableHighlight.size === 0}
            className="auth-btn auth-btn--outline inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium"
          >
            Add <FiChevronRight className="h-3.5 w-3.5 max-sm:rotate-90" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => remove([...chosenHighlight])}
            disabled={chosenHighlight.size === 0}
            className="auth-btn auth-btn--outline inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium"
          >
            <FiChevronLeft className="h-3.5 w-3.5 max-sm:rotate-90" aria-hidden="true" /> Remove
          </button>
        </div>
        <TagList
          id="tags-chosen"
          title="Chosen tags"
          tags={chosen}
          filter={chosenFilter}
          onFilter={setChosenFilter}
          highlighted={chosenHighlight}
          onToggle={toggle(setChosenHighlight)}
          onMove={remove}
          emptyText="No tags chosen yet."
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="showcase-muted text-xs">Click tags to select them, then Add or Remove. Double-click moves one tag.</p>
        <button type="button" onClick={() => setAdding(true)} className="auth-btn auth-btn--outline inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium">
          <FiPlus className="h-3.5 w-3.5" aria-hidden="true" /> Add Tag
        </button>
      </div>

      <Modal open={adding} title="Add Tag" onClose={() => !saving && setAdding(false)}>
        {/* Not a nested <form>: this dialog renders inside the product form, and forms can't nest. */}
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="new-tag-name" className="text-sm font-medium">
              Tag Name
            </label>
            <input
              id="new-tag-name"
              type="text"
              maxLength={60}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && createTag(e)}
              className="checkout-input rounded-lg px-3 py-2.5 text-sm"
            />
          </div>
          <div className="flex justify-end gap-3">
            <button type="button" onClick={() => setAdding(false)} disabled={saving} className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
              Cancel
            </button>
            <button type="button" onClick={createTag} disabled={saving || !newName.trim()} className="auth-btn auth-btn--primary rounded-full px-5 py-2 text-sm font-medium">
              {saving ? "Adding..." : "Add Tag"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
