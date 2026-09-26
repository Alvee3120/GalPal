"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FiLogOut, FiMenu, FiX } from "react-icons/fi";
import { logoutAction } from "@/app/actions/auth";
import { notify } from "@/lib/notify";
import { navFor, ROLE_LABEL } from "@/lib/dashboardNav";
import DashboardNavList from "./DashboardNavList";

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"]), input';

// Shared by the desktop sidebar and the mobile drawer so both keep the logout button fixed at the bottom, outside
// the scrollable nav area, instead of drifting away with the links.
function LogoutButton({ onLogout, loggingOut }) {
  return (
    <button
      type="button"
      onClick={onLogout}
      disabled={loggingOut}
      className="dashboard-nav-link dashboard-nav-link--danger flex shrink-0 items-center gap-3 rounded-full px-4 py-2.5 text-sm font-medium"
    >
      <FiLogOut className="h-5 w-5 shrink-0" aria-hidden="true" />
      {loggingOut ? "Logging out..." : "Logout"}
    </button>
  );
}

// The dashboard's persistent chrome: a left sidebar on desktop, a slide-in drawer (same mechanics as
// MobileFilterDrawer.jsx: focus trap, Escape, backdrop click, body-scroll lock) below lg, and a topbar with the
// menu button + a "back to site" link. `user`/`navItems` come from the server layout (real session + role).
export default function DashboardShell({ user, children }) {
  const router = useRouter();
  const navItems = navFor(user.role);
  const [open, setOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [avatarFailed, setAvatarFailed] = useState(false);
  const panelRef = useRef(null);
  const closeRef = useRef(null);
  const menuButtonRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        menuButtonRef.current?.focus();
      } else if (e.key === "Tab") {
        const nodes = [...(panelRef.current?.querySelectorAll(FOCUSABLE) ?? [])];
        if (!nodes.length) return;
        const first = nodes[0];
        const last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function handleLogout() {
    if (loggingOut) return;
    setLoggingOut(true);
    try {
      await logoutAction();
    } catch {
      notify.error("Logout failed. Please try again.");
      setLoggingOut(false);
      return;
    }
    setOpen(false);
    notify.success("Logged out successfully.");
    router.push("/");
    router.refresh();
  }

  const profile = (
    <div className="dashboard-profile flex shrink-0 items-center gap-3 rounded-2xl p-3">
      {user.avatar && !avatarFailed ? (
        // The profile photo (GET /account/profile/ avatar); falls back to the initial if it's missing or fails to load.
        // eslint-disable-next-line @next/next/no-img-element -- remote avatar at a fixed small size
        <img src={user.avatar} alt="" onError={() => setAvatarFailed(true)} className="h-10 w-10 shrink-0 rounded-full object-cover" />
      ) : (
        <span className="dashboard-profile__avatar flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold" aria-hidden="true">
          {user.full_name?.trim().charAt(0).toUpperCase() || "?"}
        </span>
      )}
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold">{user.full_name}</p>
        <p className="showcase-muted truncate text-xs">{user.email || user.phone}</p>
        <p className="dashboard-profile__role mt-0.5 text-xs font-medium">{ROLE_LABEL[user.role] ?? user.role}</p>
      </div>
    </div>
  );

  return (
    <div className="dashboard-shell flex" style={{ minHeight: "100dvh" }}>
      {/* Desktop sidebar: fixed full-height, only the nav links area scrolls — logo, profile, and logout stay put. */}
      <aside className="dashboard-sidebar fixed inset-y-0 left-0 hidden w-64 shrink-0 flex-col gap-6 overflow-hidden p-5 lg:flex" style={{ height: "100dvh" }}>
        <Link href="/" className="inline-block shrink-0">
          <Image src="/assets/galpal/galpal-logo.svg" alt="Galpal" width={1012} height={196} className="h-9 w-auto" />
        </Link>
        {profile}
        <div className="min-h-0 flex-1 overflow-y-auto">
          <DashboardNavList items={navItems} />
        </div>
        <LogoutButton onLogout={handleLogout} loggingOut={loggingOut} />
      </aside>

      {/* Mobile drawer */}
      <div className="dashboard-drawer fixed inset-0 z-[70] lg:hidden" data-open={open} inert={!open}>
        <div className="dashboard-drawer__backdrop absolute inset-0" onClick={() => setOpen(false)} aria-hidden="true" />
        <aside
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label="Dashboard menu"
          className="dashboard-drawer__panel absolute left-0 top-0 flex h-dvh w-full max-w-xs flex-col gap-6 overflow-hidden p-5"
        >
          <div className="flex shrink-0 items-center justify-between">
            <Link href="/" className="inline-block" onClick={() => setOpen(false)}>
              <Image src="/assets/galpal/galpal-logo.svg" alt="Galpal" width={1012} height={196} className="h-9 w-auto" />
            </Link>
            <button ref={closeRef} type="button" onClick={() => setOpen(false)} aria-label="Close menu" className="cart-close flex h-9 w-9 items-center justify-center rounded-full">
              <FiX className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
          {profile}
          <div className="min-h-0 flex-1 overflow-y-auto">
            <DashboardNavList items={navItems} onNavigate={() => setOpen(false)} />
          </div>
          <LogoutButton onLogout={handleLogout} loggingOut={loggingOut} />
        </aside>
      </div>

      <div className="flex min-w-0 flex-1 flex-col lg:ml-64">
        <header className="dashboard-topbar flex items-center gap-3 px-4 py-3 sm:px-6 lg:hidden">
          <button
            ref={menuButtonRef}
            type="button"
            onClick={() => setOpen(true)}
            aria-haspopup="dialog"
            aria-label="Open dashboard menu"
            className="flex h-9 w-9 items-center justify-center rounded-full"
          >
            <FiMenu className="h-5 w-5" aria-hidden="true" />
          </button>
          <span className="custom-font text-lg">Dashboard</span>
        </header>
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
