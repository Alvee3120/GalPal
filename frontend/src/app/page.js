import { Suspense } from "react";
import Banner from "@/component/homepage/Banner";
import Marquee from "@/component/homepage/Marquee";
import CategoryShowcase, { CategoryShowcaseSkeleton } from "@/component/homepage/CategoryShowcase";
import CategoryProductShowcase, { ProductShowcaseSkeleton } from "@/component/homepage/CategoryProductShowcase";

export default function Home() {
  return (
    <main>
      <Banner />
      <Marquee />
      <Suspense fallback={<CategoryShowcaseSkeleton />}>
        <CategoryShowcase />
      </Suspense>
      <Suspense fallback={<ProductShowcaseSkeleton />}>
        <CategoryProductShowcase
          category="makeup"
          title="Top picks of the month"
          description="Our community's most-loved essentials. Nourish your skin with clean, effective beauty made for real life."
          productLimit={8}
        />
        <CategoryProductShowcase
          category="skincare"
          title="Skincare"
          description=""
          productLimit={8}
        />
      </Suspense>
    </main>
  );
}
