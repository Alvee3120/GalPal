"use client";

import { useRouter } from "next/navigation";
import { buildShopHref, PROMOTIONS } from "@/lib/shopQuery";
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


export default function ShopFilters({ categories, priceBounds, currencySymbol, searchParams }) {
  const router = useRouter();
  const go = (changes) => router.push(buildShopHref(searchParams, changes));

  return (
    <div className="flex flex-col gap-5">
      <FilterGroup title="By Categories">
        {categories.map((category) => (
          <Checkbox
            key={category.id}
            label={category.name}
            checked={searchParams.category === category.slug}
            onChange={() => go({ category: searchParams.category === category.slug ? null : category.slug })}
          />
        ))}
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
