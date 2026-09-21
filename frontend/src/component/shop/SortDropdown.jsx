"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FiCheck, FiChevronDown } from "react-icons/fi";
import { buildShopHref, SORT_OPTIONS } from "@/lib/shopQuery";

// A custom listbox, not a native <select>: on mobile, browsers render <select>'s open popup with their own
// OS-controlled UI (Android in particular blows it up to a full-width, oversized native picker) that can't be
// restyled, so the "compact pill" look from the design breaks there. This follows the same custom-dropdown
// pattern as AccountMenu (button + absolutely-positioned menu, outside-click/Escape/arrow-key handling).
export default function SortDropdown({ searchParams }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const current = SORT_OPTIONS.find((opt) => opt.value === (searchParams.ordering ?? "")) ?? SORT_OPTIONS[0];

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function select(value) {
    setOpen(false);
    buttonRef.current?.focus();
    router.push(buildShopHref(searchParams, { ordering: value || null }));
  }

  const items = () => [...(menuRef.current?.querySelectorAll('[role="option"]') ?? [])];
  const focusItem = (index) => {
    const list = items();
    if (list.length) list[(index + list.length) % list.length].focus();
  };
  const openAndFocus = (index) => {
    setOpen(true);
    requestAnimationFrame(() => focusItem(index));
  };

  const onButtonKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      openAndFocus(Math.max(0, SORT_OPTIONS.indexOf(current)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      openAndFocus(-1);
    }
  };

  const onMenuKeyDown = (e) => {
    const list = items();
    const i = list.indexOf(document.activeElement);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      focusItem(i + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      focusItem(i - 1);
    } else if (e.key === "Home") {
      e.preventDefault();
      focusItem(0);
    } else if (e.key === "End") {
      e.preventDefault();
      focusItem(-1);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      list[i]?.click();
    }
  };

  return (
    <div ref={rootRef} className="shop-sort relative inline-block">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls="shop-sort-listbox"
        onClick={() => setOpen((v) => !v)}
        onKeyDown={onButtonKeyDown}
        className="shop-sort__trigger inline-flex items-center gap-2 rounded-full py-2 pl-4 pr-3 text-sm font-medium"
      >
        {current.label}
        <FiChevronDown className={`h-4 w-4 shrink-0 transition-transform duration-150 ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>
      <ul
        ref={menuRef}
        id="shop-sort-listbox"
        role="listbox"
        aria-label="Sort by"
        onKeyDown={onMenuKeyDown}
        className={`shop-sort__menu absolute right-0 top-full z-50 mt-2 w-52 max-w-[calc(100vw-2rem)] origin-top-right rounded-lg p-1 transition duration-150 ease-out motion-reduce:transition-none ${
          open ? "visible translate-y-0 scale-100 opacity-100" : "invisible -translate-y-1 scale-95 opacity-0"
        }`}
      >
        {SORT_OPTIONS.map((opt) => (
          <li key={opt.value} role="presentation">
            <button
              type="button"
              role="option"
              aria-selected={opt.value === current.value}
              tabIndex={open ? 0 : -1}
              onClick={() => select(opt.value)}
              className="shop-sort__item flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors"
            >
              {opt.label}
              {opt.value === current.value && <FiCheck className="h-4 w-4 shrink-0" aria-hidden="true" />}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
