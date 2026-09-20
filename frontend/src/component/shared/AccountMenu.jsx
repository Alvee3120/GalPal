"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiLogOut } from "react-icons/fi";

// Account icon. Logged out: a plain link to the login page. Logged in: a dropdown with My Account / Logout.
export default function AccountMenu({ authed, icon, onLogout, className }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);

  // Close on outside click and on Escape (returning focus to the icon).
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

  if (!authed) {
    return (
      <Link href="/login" aria-label="Log in" className={className}>
        {icon}
      </Link>
    );
  }

  const items = () => [...(menuRef.current?.querySelectorAll('[role="menuitem"]') ?? [])];

  const focusItem = (index) => {
    const list = items();
    if (list.length) list[(index + list.length) % list.length].focus();
  };

  // Menu is always mounted (so it can animate) but is `invisible` while closed, which also removes it from tab order.
  const openAndFocus = (index) => {
    setOpen(true);
    requestAnimationFrame(() => focusItem(index));
  };

  const onButtonKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      openAndFocus(0);
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
    }
  };

  const itemClass = "account-menu__item block w-full rounded-md px-3 py-2 text-left text-sm transition-colors";

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="account-menu"
        onClick={() => setOpen((v) => !v)}
        onKeyDown={onButtonKeyDown}
        className={className}
      >
        {icon}
      </button>
      <div
        ref={menuRef}
        id="account-menu"
        role="menu"
        aria-label="Account"
        onKeyDown={onMenuKeyDown}
        className={`account-menu absolute right-0 top-full z-50 mt-2 w-44 max-w-[calc(100vw-1rem)] origin-top-right rounded-lg p-1 transition duration-150 ease-out motion-reduce:transition-none ${
          open ? "visible translate-y-0 scale-100 opacity-100" : "invisible -translate-y-1 scale-95 opacity-0"
        }`}
      >
        <Link href="/account" role="menuitem" tabIndex={open ? 0 : -1} onClick={() => setOpen(false)} className={itemClass}>
          My Account
        </Link>
        <button
          type="button"
          role="menuitem"
          tabIndex={open ? 0 : -1}
          onClick={async () => {
            setOpen(false);
            await onLogout();
          }}
          className={`${itemClass} account-menu__item--danger flex items-center gap-2`}
        >
          <FiLogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
          Logout
        </button>
      </div>
    </div>
  );
}
