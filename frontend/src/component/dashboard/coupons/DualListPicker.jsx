"use client";

import { useEffect, useRef, useState } from "react";
import { FiChevronLeft, FiChevronRight, FiSearch } from "react-icons/fi";
import ProductImage from "@/component/shared/ProductImage";

function Pane({ id, title, count, items, filter, onFilter, filterLabel, highlighted, onToggle, onMove, emptyText, loading, showImages }) {
  return (
    <div className="tag-pane flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl">
      <p id={`${id}-label`} className="tag-pane__head px-3 py-2.5 text-sm font-medium">
        {title} <span className="showcase-muted font-normal">({count})</span>
      </p>
      <div className="relative px-3 pb-2">
        <FiSearch className="showcase-muted pointer-events-none absolute left-5.5 top-[calc(50%-4px)] h-3.5 w-3.5 -translate-y-1/2" aria-hidden="true" />
        <input
          type="search"
          value={filter}
          onChange={(e) => onFilter(e.target.value)}
          placeholder={filterLabel}
          aria-label={`${filterLabel} (${title.toLowerCase()})`}
          className="checkout-input rounded-lg py-2 pl-8 pr-2 text-sm"
        />
      </div>
      <ul role="listbox" aria-multiselectable="true" aria-labelledby={`${id}-label`} className="tag-pane__list h-52 overflow-y-auto p-1.5">
        {loading && <li className="showcase-muted px-2 py-1.5 text-xs">Loading...</li>}
        {!loading && items.length === 0 && <li className="showcase-muted px-2 py-1.5 text-xs">{emptyText}</li>}
        {!loading &&
          items.map((item) => (
            <li key={item.id} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={highlighted.has(item.id)}
                onClick={() => onToggle(item.id)}
                onDoubleClick={() => onMove([item.id])}
                className="tag-pane__item flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm"
              >
                {showImages && (
                  <span className="cart-thumb relative h-7 w-7 shrink-0 overflow-hidden rounded">
                    <ProductImage src={item.image} alt="" tight />
                  </span>
                )}
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{item.label}</span>
                  {item.hint && <span className="showcase-muted block truncate text-[0.6875rem]">{item.hint}</span>}
                </span>
              </button>
            </li>
          ))}
      </ul>
    </div>
  );
}

// "Available / Chosen" multi-select (the TagSelector pattern, generalised): click to highlight, then Add/Remove, or
// double-click to move one. Items are { id, label, hint?, image? } with real backend ids. `options` is the full list
// for small sets (categories, brands), filtered here; for large sets pass `onSearch(query) -> Promise<items>` instead
// and the Available side is searched on the server (products).
export default function DualListPicker({ id, label, options, onSearch, chosen, onChange, showImages = false, allText }) {
  const [availableFilter, setAvailableFilter] = useState("");
  const [chosenFilter, setChosenFilter] = useState("");
  const [availableHighlight, setAvailableHighlight] = useState(new Set());
  const [chosenHighlight, setChosenHighlight] = useState(new Set());
  const [remote, setRemote] = useState({ query: null, items: [] });
  const requestId = useRef(0);

  // Server search for the Available side (debounced).
  useEffect(() => {
    if (!onSearch) return;
    const id = ++requestId.current;
    const timer = setTimeout(async () => {
      const items = await onSearch(availableFilter.trim());
      if (id === requestId.current) setRemote({ query: availableFilter.trim(), items });
    }, 300);
    return () => clearTimeout(timer);
  }, [availableFilter, onSearch]);

  const chosenIds = new Set(chosen.map((c) => c.id));
  const match = (item, q) => `${item.label} ${item.hint ?? ""}`.toLowerCase().includes(q.trim().toLowerCase());
  const pool = onSearch ? remote.items : (options ?? []).filter((o) => match(o, availableFilter));
  const available = pool.filter((o) => !chosenIds.has(o.id));
  const shownChosen = chosen.filter((c) => match(c, chosenFilter));
  const searching = Boolean(onSearch) && remote.query !== availableFilter.trim();

  const toggle = (setter) => (itemId) =>
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });

  function choose(ids) {
    const byId = new Map(pool.map((o) => [o.id, o]));
    const adding = ids.map((i) => byId.get(i)).filter(Boolean).filter((o) => !chosenIds.has(o.id));
    if (adding.length) onChange([...chosen, ...adding]);
    setAvailableHighlight(new Set());
  }

  function remove(ids) {
    const drop = new Set(ids);
    onChange(chosen.filter((c) => !drop.has(c.id)));
    setChosenHighlight(new Set());
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium">{label}</span>
      <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
        <Pane
          id={`${id}-available`}
          title="Available"
          count={available.length}
          items={available}
          filter={availableFilter}
          onFilter={setAvailableFilter}
          filterLabel="Search / filter"
          highlighted={availableHighlight}
          onToggle={toggle(setAvailableHighlight)}
          onMove={choose}
          emptyText={onSearch && !availableFilter.trim() ? "Type to search." : "Nothing to add."}
          loading={searching}
          showImages={showImages}
        />
        <div className="flex items-center justify-center gap-2 md:flex-col">
          <button
            type="button"
            onClick={() => choose([...availableHighlight])}
            disabled={availableHighlight.size === 0}
            className="auth-btn auth-btn--outline inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium"
          >
            Add <FiChevronRight className="h-3.5 w-3.5 max-md:rotate-90" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={() => remove([...chosenHighlight])}
            disabled={chosenHighlight.size === 0}
            className="auth-btn auth-btn--outline inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium"
          >
            <FiChevronLeft className="h-3.5 w-3.5 max-md:rotate-90" aria-hidden="true" /> Remove
          </button>
        </div>
        <Pane
          id={`${id}-chosen`}
          title="Chosen"
          count={chosen.length}
          items={shownChosen}
          filter={chosenFilter}
          onFilter={setChosenFilter}
          filterLabel="Search / filter"
          highlighted={chosenHighlight}
          onToggle={toggle(setChosenHighlight)}
          onMove={remove}
          emptyText={chosenFilter.trim() ? "No match." : (allText ?? "None chosen.")}
          showImages={showImages}
        />
      </div>
    </div>
  );
}
