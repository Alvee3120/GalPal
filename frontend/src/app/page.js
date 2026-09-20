import { Suspense } from "react";
import Banner from "@/component/homepage/Banner";
import Marquee from "@/component/homepage/Marquee";
import CategoryShowcase, { CategoryShowcaseSkeleton } from "@/component/homepage/CategoryShowcase";
import SkincareVideoSection from "@/component/homepage/SkincareVideoSection";
import CategoryProductShowcase, { ProductShowcaseSkeleton } from "@/component/homepage/CategoryProductShowcase";
import TrendingProducts from "@/component/homepage/TrendingProducts";
import ShoppableVideoCarousel, { VideoCarouselSkeleton } from "@/component/homepage/ShoppableVideoCarousel";

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
          title="Makeup"
          description=""
          productLimit={8}
          rows = {1}
        />
        <CategoryProductShowcase
          category="skincare"
          title="Skincare"
          description=""
          productLimit={8}
          rows = {1}
        />
      </Suspense>

       <SkincareVideoSection />

        <Suspense fallback={<ProductShowcaseSkeleton />}>
        <CategoryProductShowcase
          category="accessories"
          title="Accessories"
          description=""
          productLimit={8}
          rows = {1}
        />
      </Suspense>

      <Suspense fallback={<ProductShowcaseSkeleton />}>
        <TrendingProducts productLimit={8} />
      </Suspense>

      <Suspense fallback={<VideoCarouselSkeleton />}>
        <ShoppableVideoCarousel />
      </Suspense>
    </main>
  );
}
