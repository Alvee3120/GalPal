"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { FiChevronRight } from "react-icons/fi";

// Session-level cache of category slug -> its brands, so re-hovering a category doesn't refetch. It doubles as the
// "is it loaded yet?" flag: a slug absent from the map is still loading, one mapped to [] has finished (and is empty).
const brandsByCategory = new Map();

const categoryHref = (slug) => `/shop?category=${encodeURIComponent(slug)}`;
const brandHref = (name) => `/shop?search=${encodeURIComponent(name)}`;

// One banner: a linked image when it has a link_url (a site path or an absolute URL), otherwise a plain image.
function MegaBanner({ banner, sizes, onNavigate }) {
  if (!banner?.image) return null;
  const alt = banner.alt_text || "";
  const media = (
    <span className="mega-menu__media">
      <Image
        src={banner.image}
        alt={alt}
        fill
        unoptimized // backend media may live on a private host the Next optimizer cannot reach (as ProductImage)
        sizes={sizes}
        className="object-cover"
      />
    </span>
  );
  const link = banner.link_url;
  if (!link) return <div className="mega-menu__banner">{media}</div>;
  return link.startsWith("/") ? (
    <Link href={link} className="mega-menu__banner" aria-label={alt || "Promotion"} onClick={onNavigate}>
      {media}
    </Link>
  ) : (
    <a href={link} target="_blank" rel="noopener noreferrer" className="mega-menu__banner" aria-label={alt || "Promotion"}>
      {media}
    </a>
  );
}

// One column of links (categories, sub-categories or brands). A category with children carries an `onMouseEnter`/
// `onFocus` that swaps the panel into its second state.
function LinkList({ title, items, href, empty, onNavigate }) {
  return (
    <div className="mega-menu__col">
      <p className="mega-menu__heading">{title}</p>
      {items.length === 0 ? (
        <p className="mega-menu__empty">{empty}</p>
      ) : (
        <ul className="mega-menu__list">
          {items.map((item) => (
            <li key={item.id}>
              <Link href={href(item)} className="mega-menu__link" onMouseEnter={item.activate} onFocus={item.activate} onClick={onNavigate}>
                <span className="truncate">{item.name}</span>
                {item.hasChildren && <FiChevronRight className="mega-menu__arrow" aria-hidden="true" />}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// The Shop mega menu (component/shared/Navbar.jsx). Two states: with nothing hovered it shows all brands in column 2
// and Banner "square_1" in column 3; hovering a category that has children swaps column 2 to its sub-categories and
// column 3 to the brands inside that category, hiding Banner "square_1". Columns 4 and 5–6 (Banner "square_2" and the
// wide banner) are the same in both states.
export default function MegaMenu({ categories = [], brands = [], banners = [], onNavigate }) {
  const [active, setActive] = useState(null); // the hovered category that has children, or null
  const [, bump] = useState(0); // re-render once a category's brands land in the session cache
  const inFlight = useRef(new Set());

  const bannersBySlot = (banners ?? []).reduce((acc, banner) => ({ ...acc, [banner.slot]: banner }), {});
  const activeSlug = active?.slug ?? null;
  const activeBrands = activeSlug ? (brandsByCategory.get(activeSlug) ?? null) : null;

  // Fetch the hovered category's brands into the session cache (at most once per slug). Nothing is set synchronously
  // in the effect body — the re-render is requested from the promise callback, so there is no cascading render.
  useEffect(() => {
    if (!activeSlug || brandsByCategory.has(activeSlug) || inFlight.current.has(activeSlug)) return;
    inFlight.current.add(activeSlug);
    let cancelled = false;
    fetch(`/api/brands?category=${encodeURIComponent(activeSlug)}&page_size=100`, { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => brandsByCategory.set(activeSlug, Array.isArray(data) ? data : (data?.results ?? [])))
      .catch(() => brandsByCategory.set(activeSlug, []))
      .finally(() => {
        inFlight.current.delete(activeSlug);
        if (!cancelled) bump((n) => n + 1);
      });
    return () => {
      cancelled = true;
    };
  }, [activeSlug]);

  const categoryItems = (categories ?? []).map((category) => {
    const hasChildren = (category.children?.length ?? 0) > 0;
    return {
      id: category.id,
      name: category.name,
      slug: category.slug,
      hasChildren,
      activate: hasChildren ? () => setActive(category) : () => setActive(null),
    };
  });
  const subCategoryItems = (active?.children ?? []).map((c) => ({ id: c.id, name: c.name, slug: c.slug }));
  const allBrandItems = (brands ?? []).map((b) => ({ id: b.id, name: b.name }));

  return (
    <div className="mega-menu">
      <div className="mega-menu__grid">
        {/* col1 — categories; a category with children shows a side arrow and swaps columns 2–3 */}
        <LinkList
          title="Categories"
          items={categoryItems}
          href={(i) => categoryHref(i.slug)}
          empty="No categories"
          onNavigate={onNavigate}
        />

        {/* col2 — all brands, or the hovered category's sub-categories */}
        {active ? (
          <LinkList
            title={active.name}
            items={subCategoryItems}
            href={(i) => categoryHref(i.slug)}
            empty="No sub-categories"
            onNavigate={onNavigate}
          />
        ) : (
          <LinkList title="Brands" items={allBrandItems} href={(i) => brandHref(i.name)} empty="No brands yet" onNavigate={onNavigate} />
        )}

        {/* col3 — Banner "square_1", or the hovered category's brands (Banner "square_1" hidden in this state) */}
        {active ? (
          <div className="mega-menu__col">
            <p className="mega-menu__heading">Brands in {active.name}</p>
            {activeBrands === null ? (
              <p className="mega-menu__empty">Loading…</p>
            ) : activeBrands.length === 0 ? (
              <p className="mega-menu__empty">No brands yet</p>
            ) : (
              <ul className="mega-menu__list">
                {activeBrands.map((brand) => (
                  <li key={brand.id}>
                    <Link href={brandHref(brand.name)} className="mega-menu__link" onClick={onNavigate}>
                      <span className="truncate">{brand.name}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="mega-menu__col">
            <MegaBanner banner={bannersBySlot.square_1} sizes="(min-width: 1024px) 15vw, 25vw" onNavigate={onNavigate} />
          </div>
        )}

        {/* col4 — Banner "square_2", in both states */}
        <div className="mega-menu__col">
          <MegaBanner banner={bannersBySlot.square_2} sizes="(min-width: 1024px) 15vw, 25vw" onNavigate={onNavigate} />
        </div>

        {/* col5–6 — the wide banner, spanning two columns in both states */}
        <div className="mega-menu__col mega-menu__col--wide">
          <MegaBanner banner={bannersBySlot.wide} sizes="(min-width: 1024px) 32vw, 45vw" onNavigate={onNavigate} />
        </div>
      </div>
    </div>
  );
}
