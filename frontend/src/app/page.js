import { Suspense } from "react";
import Banner, { BannerSkeleton } from "@/component/homepage/Banner";
import Marquee from "@/component/homepage/Marquee";
import CategoryShowcase, {
  CategoryShowcaseSkeleton,
} from "@/component/homepage/CategoryShowcase";
import SkincareVideoSection from "@/component/homepage/SkincareVideoSection";
import CategoryProductShowcase, {
  ProductShowcaseSkeleton,
} from "@/component/homepage/CategoryProductShowcase";
import TrendingProducts from "@/component/homepage/TrendingProducts";
import DiscountProductShowcases from "@/component/homepage/DiscountProductShowcase";
import ShoppableVideoCarousel, {
  VideoCarouselSkeleton,
} from "@/component/homepage/ShoppableVideoCarousel";
import CustomerReviews, { CustomerReviewsSkeleton } from "@/component/homepage/CustomerReviews";

export default function Home() {
  return (
    <main>
      <Suspense fallback={<BannerSkeleton />}>
        <Banner />
      </Suspense>
      <Marquee />
      <Suspense fallback={<CategoryShowcaseSkeleton />}>
        <CategoryShowcase />
      </Suspense>

      {/* One section per live Admin discount, titled with its name; none when no discount is running. */}
      <Suspense fallback={null}>
        <DiscountProductShowcases rows={1} />
      </Suspense>

      <Suspense fallback={<ProductShowcaseSkeleton />}>
        <CategoryProductShowcase
          category="makeup"
          title="Makeup"
          description=""
          productLimit={8}
          rows={1}
        />
        <CategoryProductShowcase
          category="skincare"
          title="Skincare"
          description=""
          productLimit={8}
          rows={1}
        />
      </Suspense>

      <SkincareVideoSection />

      <Suspense fallback={<ProductShowcaseSkeleton />}>
        <CategoryProductShowcase
          category="acsosories"
          title="Accessories"
          description=""
          productLimit={8}
          rows={1}
        />
      </Suspense>


      <Suspense fallback={<ProductShowcaseSkeleton />}>
        <TrendingProducts productLimit={8} />
      </Suspense>

      <Suspense fallback={<VideoCarouselSkeleton />}>
        <ShoppableVideoCarousel />
      </Suspense>

      <Suspense fallback={<CustomerReviewsSkeleton />}>
        <CustomerReviews />
      </Suspense>
    </main>
  );
}
