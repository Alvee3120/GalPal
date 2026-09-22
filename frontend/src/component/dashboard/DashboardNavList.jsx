"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Just the nav links, shared by the desktop sidebar and the mobile drawer so the two never drift apart. This is
// deliberately ONLY the links list (no logout, no wrapper chrome) so DashboardShell can put it alone inside the
// sidebar's scrollable region while the logo/profile/logout stay fixed outside it. A link is "active" for its own
// route and any route nested under it (e.g. "My Orders" stays active on an order's own page), except "/dashboard"
// itself which only matches exactly (every dashboard route would otherwise match that prefix too).
export default function DashboardNavList({ items, onNavigate }) {
  const pathname = usePathname();
  const isActive = (href) => (href === "/dashboard" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`));

  return (
    <nav aria-label="Dashboard">
      <ul className="flex flex-col gap-1">
        {items.map(({ label, href, icon: Icon }) => (
          <li key={href}>
            <Link
              href={href}
              onClick={onNavigate}
              aria-current={isActive(href) ? "page" : undefined}
              className="dashboard-nav-link flex items-center gap-3 rounded-full px-4 py-2.5 text-sm font-medium"
            >
              <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
              {label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
