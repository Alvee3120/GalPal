"use client";

import { useRouter } from "next/navigation";
import { FiChevronDown } from "react-icons/fi";
import { buildShopHref, SORT_OPTIONS } from "@/lib/shopQuery";

export default function SortDropdown({ searchParams }) {
  const router = useRouter();
  return (
    <div className="shop-sort relative inline-flex items-center rounded-full">
      <label htmlFor="shop-sort" className="sr-only">
        Sort by
      </label>
      <select
        id="shop-sort"
        value={searchParams.ordering ?? ""}
        onChange={(e) => router.push(buildShopHref(searchParams, { ordering: e.target.value || null }))}
        className="shop-sort__select appearance-none rounded-full py-2 pl-4 pr-9 text-sm font-medium"
      >
        {SORT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <FiChevronDown className="pointer-events-none absolute right-3 h-4 w-4" aria-hidden="true" />
    </div>
  );
}
