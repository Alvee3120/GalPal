"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { FiChevronDown } from "react-icons/fi";
import { buildShopHref, parseCategories, PROMOTIONS, toggleCategoryParam } from "@/lib/shopQuery";
import PriceRangeFilter from "./PriceRangeFilter";

function FilterGroup({ title, children }) {
  return (
    <fieldset className="shop-filter-group border-t pt-0 first:border-t-0 first:pt-0">
      <legend className="mb-3 text-sm font-semibold">{title}</legend>
      {children}
    </fieldset>
  );
}

function Checkbox({ checked, onChange, label, count }) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 py-1 text-sm">
      <input type="checkbox" checked={checked} onChange={onChange} className="shop-checkbox h-4 w-4 shrink-0" />
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {typeof count === "number" && <span className="showcase-muted text-xs">{count}</span>}
    </label>
  );
}


// One level of the category tree. A category with sub-categories gets an expand/collapse chevron; its children render
// underneath, indented, and are nested the same way (the backend allows any depth). Any number of categories can be
// ticked together: a parent shows its own products plus all its sub-categories', a child only its own.
function CategoryTree({ nodes, selectedSlugs, collapsed, toggle, onSelect, depth = 0 }) {
  return (
    <ul className={depth > 0 ? "shop-category-children ml-2.5 border-l pl-3" : ""}>
      {nodes.map((category) => {
        const children = category.children ?? [];
        const expanded = !collapsed.has(category.id);
        const listId = `shop-category-${category.id}-children`;
        return (
          <li key={category.id}>
            <div className="flex items-center gap-1">
              {children.length > 0 ? (
                <button
                  type="button"
                  onClick={() => toggle(category.id)}
                  aria-expanded={expanded}
                  aria-controls={listId}
                  aria-label={`${expanded ? "Collapse" : "Expand"} ${category.name}`}
                  className="shop-category-toggle flex h-6 w-6 shrink-0 items-center justify-center rounded"
                >
                  <FiChevronDown className={`h-4 w-4 transition-transform duration-150 ${expanded ? "" : "-rotate-90"}`} aria-hidden="true" />
                </button>
              ) : (
                <span className="h-6 w-6 shrink-0" aria-hidden="true" />
              )}
              <div className={`min-w-0 flex-1 ${depth === 0 ? "font-medium" : ""}`}>
                <Checkbox label={category.name} checked={selectedSlugs.includes(category.slug)} onChange={() => onSelect(category.slug)} />
              </div>
            </div>
            {children.length > 0 && expanded && (
              <div id={listId}>
                <CategoryTree nodes={children} selectedSlugs={selectedSlugs} collapsed={collapsed} toggle={toggle} onSelect={onSelect} depth={depth + 1} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function ShopFilters({ categories, priceBounds, currencySymbol, searchParams }) {
  const router = useRouter();
  const go = (changes) => router.push(buildShopHref(searchParams, changes));
  const [collapsed, setCollapsed] = useState(() => new Set()); // every parent starts expanded
  const toggle = (id) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="flex flex-col gap-5">
      <FilterGroup title="By Categories">
        <CategoryTree
          nodes={categories}
          selectedSlugs={parseCategories(searchParams.category)}
          collapsed={collapsed}
          toggle={toggle}
          onSelect={(slug) => go({ category: toggleCategoryParam(searchParams.category, slug) })}
        />
      </FilterGroup>

      <FilterGroup title="Price">
        <PriceRangeFilter
          key={`${searchParams.price_min ?? ""}-${searchParams.price_max ?? ""}`}
          bounds={priceBounds}
          searchParams={searchParams}
          currencySymbol={currencySymbol}
        />
      </FilterGroup>

      <FilterGroup title="By Promotions">
        {PROMOTIONS.map((promo) => (
          <Checkbox
            key={promo.param}
            label={promo.label}
            checked={searchParams[promo.param] === "true"}
            onChange={() => go({ [promo.param]: searchParams[promo.param] === "true" ? null : "true" })}
          />
        ))}
      </FilterGroup>

      <FilterGroup title="Availability">
        <Checkbox
          label="In Stock"
          checked={searchParams.in_stock === "true"}
          onChange={() => go({ in_stock: searchParams.in_stock === "true" ? null : "true" })}
        />
        <Checkbox
          label="Out of Stock"
          checked={searchParams.in_stock === "false"}
          onChange={() => go({ in_stock: searchParams.in_stock === "false" ? null : "false" })}
        />
      </FilterGroup>
    </div>
  );
}
