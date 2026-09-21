import Link from "next/link";
import { buildShopHref, PROMOTIONS } from "@/lib/shopQuery";

// Plain links (no client JS needed): each tag removes just its own filter, "Clear All" drops them all.
export default function ActiveFilters({ searchParams, categories, priceBounds, currencySymbol }) {
  const tags = [];

  const category = categories.find((c) => c.slug === searchParams.category);
  if (category) tags.push({ key: "category", label: category.name, href: buildShopHref(searchParams, { category: null }) });

  const min = searchParams.price_min ? Number(searchParams.price_min) : null;
  const max = searchParams.price_max ? Number(searchParams.price_max) : null;
  if (min !== null || max !== null) {
    tags.push({
      key: "price",
      label: `Price: ${currencySymbol}${(min ?? priceBounds.min).toLocaleString()} - ${currencySymbol}${(max ?? priceBounds.max).toLocaleString()}`,
      href: buildShopHref(searchParams, { price_min: null, price_max: null }),
    });
  }

  for (const promo of PROMOTIONS) {
    if (searchParams[promo.param] === "true") {
      tags.push({ key: promo.param, label: promo.label, href: buildShopHref(searchParams, { [promo.param]: null }) });
    }
  }

  if (searchParams.in_stock === "true") tags.push({ key: "in_stock", label: "In Stock", href: buildShopHref(searchParams, { in_stock: null }) });
  if (searchParams.in_stock === "false") tags.push({ key: "in_stock", label: "Out of Stock", href: buildShopHref(searchParams, { in_stock: null }) });

  if (tags.length === 0) return null;

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      <span className="text-sm font-medium">Active Filter</span>
      {tags.map((tag) => (
        <Link key={tag.key} href={tag.href} className="shop-tag inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium">
          {tag.label}
          <span aria-hidden="true">×</span>
        </Link>
      ))}
      <Link href="/shop" className="shop-clear-all text-xs font-medium underline underline-offset-4">
        Clear All
      </Link>
    </div>
  );
}
