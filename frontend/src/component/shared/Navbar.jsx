"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import AccountMenu from "./AccountMenu";
import ProductImage from "./ProductImage";
import { useCart } from "@/component/cart/CartProvider";
import { logoutAction } from "@/app/actions/auth";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";

const SEARCH_DEBOUNCE_MS = 350;
const SEARCH_RESULT_LIMIT = 5;

const links = [
  { href: "/", label: "Home" },
  { href: "/shop", label: "Shop" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

const iconClass = "h-5 w-5";

function Icon({ children }) {
  return (
    <svg
      className={iconClass}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const searchIcon = (
  <Icon>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </Icon>
);

const closeIcon = (
  <Icon>
    <path d="M6 6l12 12M18 6 6 18" />
  </Icon>
);

const actions = [
  {
    href: "/account",
    label: "Account",
    icon: (
      <Icon>
        <circle cx="12" cy="8" r="4" />
        <path d="M4 21c0-4 4-6 8-6s8 2 8 6" />
      </Icon>
    ),
  },
  {
    href: "/cart",
    label: "Cart",
    icon: (
      <Icon>
        <path d="M3 4h2l2.4 11h10.2L20 7H6" />
        <circle cx="9" cy="19.5" r="1.2" />
        <circle cx="17" cy="19.5" r="1.2" />
      </Icon>
    ),
  },
];

function SearchForm({
  id,
  inputRef,
  query,
  setQuery,
  onSubmit,
  onClose,
  className,
}) {
  return (
    <form role="search" onSubmit={onSubmit} className={className}>
      {/* Icon (and close button) overlaid on the input via absolute positioning, the same proven pattern used
          for every other search box in this app (e.g. component/dashboard/CceOrderManagement.jsx) — not flex
          siblings, so there is no row for the input to ever wrap out of. */}
      <div className="search-field">
        <span className="search-field__icon" aria-hidden="true">
          {searchIcon}
        </span>
        <input
          ref={inputRef}
          id={id}
          type="text"
          name="q"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search products..."
          aria-label="Search products"
          autoComplete="off"
          enterKeyHint="search"
          className={`search-field__input${onClose ? " search-field__input--with-close" : ""}`}
        />
        {onClose && (
          <button type="button" onClick={onClose} aria-label="Close search" className="search-field__close navbar-action transition-colors">
            {closeIcon}
          </button>
        )}
      </div>
    </form>
  );
}

// Up to SEARCH_RESULT_LIMIT live results below the search input, reused for both the desktop (floating, absolute)
// and mobile (in-flow, inside the sliding search panel) instances — `floating` picks which. Backed by the
// EXISTING public product list (GET /products/?search=, via the /api/products proxy — no new search endpoint),
// so a result is exactly what the Shop page/Product Details already know about: same id, slug, price fields.
function SearchResults({ results, loading, fresh, count, query, currencySymbol, onNavigate, floating = true }) {
  const shown = results.slice(0, SEARCH_RESULT_LIMIT);
  const showViewAll = count > SEARCH_RESULT_LIMIT;
  const showLoading = loading || !fresh;

  return (
    <div
      role="listbox"
      aria-label="Search results"
      className={`search-dropdown flex flex-col overflow-hidden rounded-2xl ${floating ? "absolute inset-x-0 top-full z-50 mt-2" : "mt-3"}`}
    >
      {showLoading ? (
        <p className="showcase-muted px-4 py-6 text-center text-sm">Searching...</p>
      ) : shown.length === 0 ? (
        <p className="showcase-muted px-4 py-6 text-center text-sm">No products found.</p>
      ) : (
        <>
          <ul className="flex flex-col">
            {shown.map((product) => {
              const discounted = product.on_sale && product.regular_price !== product.effective_price;
              return (
                <li key={product.id} role="option" aria-selected="false">
                  <Link href={`/products/${product.slug}`} onClick={onNavigate} className="search-dropdown__item flex items-center gap-3 px-4 py-2.5">
                    <span className="cart-thumb relative h-11 w-11 shrink-0 overflow-hidden rounded-lg">
                      <ProductImage src={product.feature_image} alt="" tight />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{product.name}</span>
                      <span className="flex items-baseline gap-1.5 text-sm">
                        <span className="font-semibold">{formatPrice(product.effective_price, currencySymbol)}</span>
                        {discounted && <span className="showcase-muted text-xs line-through">{formatPrice(product.regular_price, currencySymbol)}</span>}
                      </span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
          {showViewAll && (
            <Link href={`/shop?search=${encodeURIComponent(query)}`} onClick={onNavigate} className="search-dropdown__viewall block px-4 py-2.5 text-center text-sm font-medium">
              View All →
            </Link>
          )}
        </>
      )}
    </div>
  );
}

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const isHome = pathname === "/";
  const { itemCount, openCart, currencySymbol } = useCart();

  // Session state comes from the auth cookies (via /api/session); re-checked on every navigation,
  // so it updates right after login or logout.
  const [authed, setAuthed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/session", { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => !cancelled && setAuthed(Boolean(data.authenticated)))
      .catch(() => !cancelled && setAuthed(false));
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const handleLogout = async () => {
    try {
      await logoutAction();
    } catch {
      notify.error("Logout failed. Please try again.");
      return;
    }
    setAuthed(false);
    notify.success("Logged out successfully.");
    router.refresh();
  };

  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [query, setQuery] = useState("");

  // Live search dropdown (desktop always-visible box + the mobile slide-down panel share this state).
  const [searchResults, setSearchResults] = useState([]);
  const [searchCount, setSearchCount] = useState(0);
  const [searchLoading, setSearchLoading] = useState(false);
  const [resultsQuery, setResultsQuery] = useState(""); // the query `searchResults` actually answers
  const [desktopDropdownClosed, setDesktopDropdownClosed] = useState(false);
  const searchRequestId = useRef(0);
  const desktopSearchRef = useRef(null);

  const searchButtonRef = useRef(null);
  const mobileInputRef = useRef(null);

  const closeSearch = () => setIsSearchOpen(false);

  // Typing always (re)reveals the desktop dropdown; only an explicit close (outside click, Escape, selecting a
  // result, View All, submit) hides it again while a query is still present.
  function handleQueryChange(value) {
    setQuery(value);
    setDesktopDropdownClosed(false);
  }

  // Debounced live search, backed by the EXISTING public product list (GET /products/?search=&page_size=,
  // apps.catalog.views_product.PublicProductViewSet — see /api/products/route.js). Nothing is set synchronously
  // in this effect's own body — every setState happens inside the debounce timer's callback — and stale
  // responses (a slower earlier request resolving after a newer one) are dropped via the request-id guard.
  useEffect(() => {
    const q = query.trim();
    if (!q) return;
    const id = ++searchRequestId.current;
    const timer = setTimeout(async () => {
      setSearchLoading(true);
      try {
        const res = await fetch(`/api/products?search=${encodeURIComponent(q)}&page_size=${SEARCH_RESULT_LIMIT}`, { cache: "no-store" });
        const data = await res.json().catch(() => null);
        if (id !== searchRequestId.current) return;
        setSearchResults(res.ok && Array.isArray(data?.results) ? data.results : []);
        setSearchCount(res.ok ? (data?.count ?? 0) : 0);
        setResultsQuery(q);
      } catch {
        if (id === searchRequestId.current) {
          setSearchResults([]);
          setSearchCount(0);
          setResultsQuery(q);
        }
      } finally {
        if (id === searchRequestId.current) setSearchLoading(false);
      }
    }, SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [query]);

  // Desktop dropdown only: outside click / Escape close it (mobile's equivalent is the whole search panel's own
  // existing open/close lifecycle below).
  const showDesktopDropdown = query.trim() !== "" && !desktopDropdownClosed;
  useEffect(() => {
    if (!showDesktopDropdown) return;
    const onPointerDown = (e) => {
      if (!desktopSearchRef.current?.contains(e.target)) setDesktopDropdownClosed(true);
    };
    const onKeyDown = (e) => {
      if (e.key === "Escape") setDesktopDropdownClosed(true);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [showDesktopDropdown]);

  // Search and the mobile menu are mutually exclusive.
  const toggleSearch = () => {
    setOpen(false);
    setIsSearchOpen((v) => !v);
  };

  const toggleMenu = () => {
    setIsSearchOpen(false);
    setOpen((o) => !o);
  };

  // Enter/submit behaves like "View All": the existing Shop page filter architecture (lib/shopQuery.js,
  // lib/shopData.js) already reads a `search` query param, so this is the same destination the dropdown's own
  // "View All" link uses, not a second search results page.
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    router.push(`/shop?search=${encodeURIComponent(q)}`);
    setQuery("");
    setDesktopDropdownClosed(true);
    closeSearch();
  };

  // After navigating away from a search (a result, View All, or Enter/submit — see handleSearchSubmit above),
  // the input clears itself and is ready for a fresh search rather than keeping the last query visible.
  function handleDesktopResultNavigate() {
    setQuery("");
    setDesktopDropdownClosed(true);
  }

  function handleMobileResultNavigate() {
    setQuery("");
    closeSearch();
  }

  // Mobile/tablet only: focus the dropdown input when it opens.
  useEffect(() => {
    if (isSearchOpen) mobileInputRef.current?.focus({ preventScroll: true });
  }, [isSearchOpen]);

  // Escape closes the search and returns focus to the trigger.
  useEffect(() => {
    if (!isSearchOpen) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        setIsSearchOpen(false);
        searchButtonRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isSearchOpen]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Transparent only on the homepage, at the top, with the mobile menu closed.
  const transparent = isHome && !scrolled && !open;
  const tinted = isHome && (scrolled || open);

  const position = isHome ? "fixed inset-x-0 top-0" : "sticky top-0";
  // Colors for each state are defined in globals.css
  const surface = transparent
    ? "navbar--overlay"
    : tinted
      ? "navbar--scrolled"
      : "navbar--solid";

  // The dashboard has its own header/sidebar (DashboardShell) — after every hook above, so the hook order never
  // changes between renders of this component.
  if (pathname.startsWith("/dashboard")) return null;

  return (
    <header
      className={`navbar ${position} z-50 transition-[background-color,color,box-shadow,backdrop-filter] duration-300 ease-out motion-reduce:transition-none ${surface}`}
    >
      <nav
        aria-label="Main"
        className="mx-auto flex h-16 w-full max-w-7xl items-center px-4 sm:px-6 lg:px-8"
      >
        <ul className="order-1 hidden flex-1 items-center gap-6 whitespace-nowrap text-sm font-medium md:flex lg:gap-8">
          {links.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                aria-current={pathname === l.href ? "page" : undefined}
                className="opacity-90 transition-opacity hover:opacity-100 aria-[current=page]:opacity-100 aria-[current=page]:underline aria-[current=page]:underline-offset-8"
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
        <Link
          href="/"
          className="order-1 shrink-0 md:order-2 md:mx-6"
          onClick={() => {
            setOpen(false);
            closeSearch();
          }}
        >
          <Image
            src="/assets/galpal/navlogo.svg"
            alt="Galpal"
            width={327}
            height={226}
            priority
            className="h-10 w-auto"
          />
        </Link>

        <div className="order-3 ml-auto flex min-w-0 items-center justify-end gap-1 pl-4 sm:gap-2 md:ml-0 md:flex-1">
          {/* Desktop (lg+): compact always-visible search, right of the centered links, before the action icons */}
          <div ref={desktopSearchRef} className="relative mr-1 hidden w-48 min-w-0 shrink lg:block xl:w-60">
            <SearchForm id="search-desktop" query={query} setQuery={handleQueryChange} onSubmit={handleSearchSubmit} className="w-full" />
            {showDesktopDropdown && (
              <SearchResults
                results={searchResults}
                loading={searchLoading}
                fresh={resultsQuery === query.trim()}
                count={searchCount}
                query={query.trim()}
                currencySymbol={currencySymbol}
                onNavigate={handleDesktopResultNavigate}
              />
            )}
          </div>
          {/* Below lg: icon toggles the dropdown search under the navbar */}
          <button
            ref={searchButtonRef}
            type="button"
            aria-label="Search"
            aria-expanded={isSearchOpen}
            onClick={toggleSearch}
            className="navbar-action rounded-full p-2 transition-colors lg:hidden"
          >
            {searchIcon}
          </button>
          {actions.map((a) =>
            a.href === "/account" ? (
              <AccountMenu
                key={a.href}
                authed={authed}
                icon={a.icon}
                onLogout={handleLogout}
                className="navbar-action rounded-full p-2 transition-colors"
              />
            ) : a.href === "/cart" ? (
              // Opens the shared cart drawer instead of navigating
              <button
                key={a.href}
                type="button"
                aria-label={itemCount > 0 ? `Cart, ${itemCount} ${itemCount === 1 ? "item" : "items"}` : "Cart"}
                aria-haspopup="dialog"
                onClick={() => {
                  setOpen(false);
                  closeSearch();
                  openCart();
                }}
                className="navbar-action relative rounded-full p-2 transition-colors"
              >
                {a.icon}
                {itemCount > 0 && (
                  <span aria-hidden="true" className="cart-count absolute -right-0.5 -top-0.5 flex h-[1.125rem] min-w-[1.125rem] items-center justify-center rounded-full px-1 text-[0.625rem] font-semibold leading-none">
                    {itemCount > 99 ? "99+" : itemCount}
                  </span>
                )}
              </button>
            ) : (
            <Link
              key={a.href}
              href={a.href}
              aria-label={a.label}
              className="navbar-action rounded-full p-2 transition-colors"
            >
              {a.icon}
            </Link>
            ),
          )}
          <button
            type="button"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="mobile-menu"
            onClick={toggleMenu}
            className="navbar-action rounded-full p-2 transition-colors md:hidden"
          >
            <Icon>
              {open ? (
                <path d="M6 6l12 12M18 6 6 18" />
              ) : (
                <path d="M4 7h16M4 12h16M4 17h16" />
              )}
            </Icon>
          </button>
        </div>
      </nav>

      {/* Below lg: dropdown panel directly under the navbar (overlays, never pushes it) */}
      <div
        inert={!isSearchOpen}
        aria-hidden={!isSearchOpen}
        className={`search-panel absolute inset-x-0 top-full grid transition-[grid-template-rows,opacity] duration-300 ease-out motion-reduce:transition-none lg:hidden ${
          isSearchOpen
            ? "grid-rows-[1fr] opacity-100"
            : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="overflow-hidden">
          <SearchForm
            id="search-mobile"
            inputRef={mobileInputRef}
            query={query}
            setQuery={handleQueryChange}
            onSubmit={handleSearchSubmit}
            onClose={closeSearch}
            className="mx-auto w-full max-w-7xl px-4 py-3 sm:px-6"
          />
          {isSearchOpen && query.trim() !== "" && (
            <div className="mx-auto w-full max-w-7xl px-4 pb-3 sm:px-6">
              <SearchResults
                results={searchResults}
                loading={searchLoading}
                fresh={resultsQuery === query.trim()}
                count={searchCount}
                query={query.trim()}
                currencySymbol={currencySymbol}
                onNavigate={handleMobileResultNavigate}
                floating={false}
              />
            </div>
          )}
        </div>
      </div>

      {open && (
        <ul
          id="mobile-menu"
          className="navbar-mobile-menu px-4 py-2 text-base font-medium md:hidden"
        >
          {links.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                onClick={() => setOpen(false)}
                aria-current={pathname === l.href ? "page" : undefined}
                className="block py-3 aria-[current=page]:underline aria-[current=page]:underline-offset-8"
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </header>
  );
}
