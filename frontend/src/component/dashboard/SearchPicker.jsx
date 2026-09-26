"use client";

import { useEffect, useRef, useState } from "react";
import { FiSearch, FiX } from "react-icons/fi";
import ProductImage from "@/component/shared/ProductImage";

// Pick ONE thing from a server search (products, users): type to search, choose a result, and the choice shows as a
// card with a Change (✕) button. `search(query) -> Promise<[{ id, label, hint?, image? }]>`; the chosen item's real
// backend id is what the caller sends.
export default function SearchPicker({ id, label, placeholder, search, value, onChange, showImages = false, required = false, disabled = false }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState({ query: null, items: [] });
  const rootRef = useRef(null);
  const requestId = useRef(0);

  useEffect(() => {
    if (!open) return;
    const reqId = ++requestId.current;
    const timer = setTimeout(async () => {
      const items = await search(query.trim());
      if (reqId === requestId.current) setResults({ query: query.trim(), items });
    }, 300);
    return () => clearTimeout(timer);
  }, [query, open, search]);

  useEffect(() => {
    if (!open) return;
    const close = (e) => !rootRef.current?.contains(e.target) && setOpen(false);
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [open]);

  const loading = open && results.query !== query.trim();
  const thumb = (item, size) =>
    showImages && (
      <span className={`cart-thumb relative ${size} shrink-0 overflow-hidden rounded-lg`}>
        <ProductImage src={item.image} alt="" tight />
      </span>
    );

  return (
    <div ref={rootRef} className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label} {required && <span aria-hidden="true">*</span>}
      </label>
      {value ? (
        <div className="picker-choice flex items-center gap-3 rounded-lg px-3 py-2.5">
          {thumb(value, "h-10 w-10")}
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{value.label}</p>
            {value.hint && <p className="showcase-muted truncate text-xs">{value.hint}</p>}
          </div>
          {!disabled && (
            <button
              type="button"
              onClick={() => {
                onChange(null);
                setQuery("");
                setOpen(true);
              }}
              title={`Change ${label.toLowerCase()}`}
              aria-label={`Change ${label.toLowerCase()}`}
              className="icon-action flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
            >
              <FiX className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      ) : (
        <div className="relative">
          <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
          <input
            id={id}
            type="search"
            role="combobox"
            aria-expanded={open}
            aria-controls={`${id}-results`}
            autoComplete="off"
            value={query}
            onFocus={() => setOpen(true)}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
            placeholder={placeholder}
            className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
          />
          {open && (
            <ul id={`${id}-results`} role="listbox" className="shop-sort__menu absolute left-0 right-0 top-full z-40 mt-1.5 max-h-72 overflow-y-auto rounded-lg p-1">
              {loading && <li className="showcase-muted px-3 py-2 text-sm">Searching...</li>}
              {!loading && results.items.length === 0 && <li className="showcase-muted px-3 py-2 text-sm">No matches.</li>}
              {!loading &&
                results.items.map((item) => (
                  <li key={item.id} role="presentation">
                    <button
                      type="button"
                      role="option"
                      aria-selected="false"
                      onClick={() => {
                        onChange(item);
                        setOpen(false);
                      }}
                      className="shop-sort__item flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm"
                    >
                      {thumb(item, "h-9 w-9")}
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{item.label}</span>
                        {item.hint && <span className="showcase-muted block truncate text-xs">{item.hint}</span>}
                      </span>
                    </button>
                  </li>
                ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
