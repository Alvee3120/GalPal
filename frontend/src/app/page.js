import { Suspense } from "react";
import Banner from "@/component/homepage/Banner";
import Marquee from "@/component/homepage/Marquee";
import CategoryShowcase, { CategoryShowcaseSkeleton } from "@/component/homepage/CategoryShowcase";

export default function Home() {
  return (
    <main>
      <Banner />
      <Marquee />
      <Suspense fallback={<CategoryShowcaseSkeleton />}>
        <CategoryShowcase />
      </Suspense>
    </main>
  );
}
