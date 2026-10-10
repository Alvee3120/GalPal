import { Suspense } from "react";
import Banner, { BannerSkeleton } from "@/component/homepage/Banner";
import Marquee from "@/component/homepage/Marquee";
import CategoryShowcase, {
  CategoryShowcaseSkeleton,
} from "@/component/homepage/CategoryShowcase";
import SkincareVideoSection from "@/component/homepage/SkincareVideoSection";
import { ProductShowcaseSkeleton } from "@/component/homepage/CategoryProductShowcase";
import HomepageCategorySections from "@/component/homepage/HomepageCategorySections";
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

      {/* Product sections the Admin placed before the skincare video (Admin → Homepage Sections): categories and
          Trending / New Arrivals / Bestsellers. */}
      <Suspense fallback={<ProductShowcaseSkeleton />}>
        <HomepageCategorySections position="before_video" />
      </Suspense>

      <SkincareVideoSection />

      {/* …and the ones placed after it. */}
      <Suspense fallback={<ProductShowcaseSkeleton />}>
        <HomepageCategorySections position="after_video" />
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
