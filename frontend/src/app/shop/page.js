import { Suspense } from "react";
import PageHero from "@/component/shared/PageHero";
import ShopFilters from "@/component/shop/ShopFilters";
import MobileFilterDrawer from "@/component/shop/MobileFilterDrawer";
import ActiveFilters from "@/component/shop/ActiveFilters";
import SortDropdown from "@/component/shop/SortDropdown";
import ShopProductGrid, { ShopProductGridSkeleton } from "@/component/shop/ShopProductGrid";
import ShopPagination from "@/component/shop/ShopPagination";
import NotifyOnMount from "@/component/shared/NotifyOnMount";
import { getShopCategories, getShopPriceBounds, getShopProducts } from "@/lib/shopData";
import { getCurrencySymbol } from "@/lib/siteSettings";
import { FILTER_KEYS, SHOP_PAGE_SIZE } from "@/lib/shopQuery";

export const metadata = { title: "Shop | GalPal" };

async function ShopResults({ searchParams, categories, priceBounds, currencySymbol }) {
  const { products, count, page, error } = await getShopProducts(searchParams);
  const totalPages = Math.max(1, Math.ceil(count / SHOP_PAGE_SIZE));
  const start = count === 0 ? 0 : (page - 1) * SHOP_PAGE_SIZE + 1;
  const end = Math.min(page * SHOP_PAGE_SIZE, count);

  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">{count === 0 ? "No results" : `Showing ${start}-${end} of ${count} results`}</p>
        <div className="flex items-center gap-2">
          <span className="text-sm">Sort by :</span>
          <SortDropdown searchParams={searchParams} />
        </div>
      </div>

      <ActiveFilters searchParams={searchParams} categories={categories} priceBounds={priceBounds} currencySymbol={currencySymbol} />

      {error ? (
        <>
          <div className="shop-empty rounded-2xl px-6 py-16 text-center">
            <p className="custom-font text-2xl">We couldn&apos;t load these products right now.</p>
          </div>
          <NotifyOnMount message="Unable to load products." />
        </>
      ) : (
        <>
          <ShopProductGrid products={products} currencySymbol={currencySymbol} />
          <ShopPagination page={page} totalPages={totalPages} searchParams={searchParams} />
        </>
      )}
    </>
  );
}

// /shop?category=&price_min=&price_max=&is_new_arrival=&is_bestseller=&on_sale=&in_stock=&ordering=&page=
export default async function ShopPage({ searchParams }) {
  const resolvedParams = await searchParams;
  const [categories, priceBounds, currencySymbol] = await Promise.all([getShopCategories(), getShopPriceBounds(), getCurrencySymbol()]);
  const activeCount = FILTER_KEYS.filter((key) => resolvedParams[key]).length;
  const filterProps = { categories, priceBounds, currencySymbol, searchParams: resolvedParams };

  return (
    <main>
      <PageHero title="Shop" />

      <div className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <div className="mb-5 lg:hidden">
          <MobileFilterDrawer activeCount={activeCount} {...filterProps} />
        </div>

        <div className="lg:grid lg:grid-cols-[15.5rem_1fr] lg:items-start lg:gap-10">
          <aside className="shop-sidebar sticky top-20 hidden rounded-2xl p-5 lg:block">
            <h2 className="mb-5 text-base font-semibold">Filter Options</h2>
            <ShopFilters {...filterProps} />
          </aside>

          <div className="min-w-0">
            <Suspense fallback={<ShopProductGridSkeleton />}>
              <ShopResults searchParams={resolvedParams} categories={categories} priceBounds={priceBounds} currencySymbol={currencySymbol} />
            </Suspense>
          </div>
        </div>
      </div>
    </main>
  );
}
