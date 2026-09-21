"use client";

import { useEffect, useRef, useState } from "react";
import { FiCheck, FiChevronDown } from "react-icons/fi";

// A custom listbox used instead of a native <select> for long lists (e.g. the 64 checkout cities): the browser draws
// a native <select>'s open popup itself, oversized and unstyleable, especially on mobile. Same pattern as
// SortDropdown/AccountMenu (button + menu, outside-click/Escape/arrow keys), plus type-ahead by first letter and a
// height-capped, scrollable menu. `id` goes on the button so a <label htmlFor={id}> names it.
export default function SelectField({ id, value, onChange, options, placeholder, name, className = "" }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const listboxId = `${id}-listbox`;

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const items = () => [...(menuRef.current?.querySelectorAll('[role="option"]') ?? [])];
  const focusItem = (index) => {
    const list = items();
    if (list.length) list[(index + list.length) % list.length].focus();
  };
  // Opening always moves focus into the list (the chosen option, or the first), so Escape, arrows and
  // type-ahead work the same whether it was opened by mouse, touch or keyboard.
  const openAndFocus = (index) => {
    setOpen(true);
    requestAnimationFrame(() => {
      focusItem(index);
      menuRef.current?.scrollIntoView({ block: "nearest" });
    });
  };

  function choose(option) {
    setOpen(false);
    buttonRef.current?.focus();
    onChange(option);
  }

  const onButtonKeyDown = (e) => {
    if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openAndFocus(Math.max(0, options.indexOf(value)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      openAndFocus(-1);
    }
  };

  const onMenuKeyDown = (e) => {
    const list = items();
    const i = list.indexOf(document.activeElement);
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      buttonRef.current?.focus();
    } else if (e.key === "ArrowDown") {
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
    } else if (e.key === "Tab") {
      setOpen(false);
    } else if (e.key.length === 1 && /\S/.test(e.key)) {
      const letter = e.key.toLowerCase();
      const from = i + 1;
      const next = [...options.keys()].map((k) => (k + from) % options.length).find((k) => options[k].toLowerCase().startsWith(letter));
      if (next !== undefined) focusItem(next);
    }
  };

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      {name && <input type="hidden" name={name} value={value} />}
      <button
        ref={buttonRef}
        id={id}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        onClick={() => (open ? setOpen(false) : openAndFocus(Math.max(0, options.indexOf(value))))}
        onKeyDown={onButtonKeyDown}
        className="checkout-input flex items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-left text-sm"
      >
        <span className={value ? "" : "showcase-muted"}>{value || placeholder}</span>
        <FiChevronDown className={`h-4 w-4 shrink-0 transition-transform duration-150 ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>
      <ul
        ref={menuRef}
        id={listboxId}
        role="listbox"
        aria-labelledby={id}
        onKeyDown={onMenuKeyDown}
        className={`shop-sort__menu absolute left-0 top-full z-50 mt-1.5 max-h-56 w-full origin-top overflow-y-auto overscroll-contain rounded-lg p-1 transition duration-150 ease-out motion-reduce:transition-none ${
          open ? "visible translate-y-0 scale-100 opacity-100" : "invisible -translate-y-1 scale-95 opacity-0"
        }`}
      >
        {options.map((option) => (
          <li key={option} role="presentation">
            <button
              type="button"
              role="option"
              aria-selected={option === value}
              tabIndex={open ? 0 : -1}
              onClick={() => choose(option)}
              className="shop-sort__item flex w-full items-center justify-between gap-2 rounded-md px-3 py-1.5 text-left text-sm transition-colors"
            >
              {option}
              {option === value && <FiCheck className="h-4 w-4 shrink-0" aria-hidden="true" />}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
