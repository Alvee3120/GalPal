import { getApprovedReviews } from "@/lib/reviewsData";
import SectionHeader from "@/component/shared/SectionHeader";
import ReviewMarquee from "./ReviewMarquee";

const sectionClass = "w-full overflow-hidden py-7 md:py-10";
const headerClass = "mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8";

// Homepage testimonials: the newest APPROVED reviews from the existing public reviews API (it never returns pending
// or rejected ones). Nothing is rendered without real reviews — no placeholder testimonials.
export default async function CustomerReviews() {
  const reviews = await getApprovedReviews(16);
  if (reviews.length === 0) return null;
  return (
    <section aria-label="Customer reviews" className={sectionClass}>
      <div className={headerClass}>
        <SectionHeader
          title="Loved by Our Customers"
          description="Real reviews from GalPal customers."
          titleClassName="max-w-[12em] lg:max-w-none lg:whitespace-nowrap" // one line on desktop
        />
      </div>
      <ReviewMarquee reviews={reviews} />
    </section>
  );
}

export function CustomerReviewsSkeleton() {
  return (
    <section aria-label="Loading customer reviews" aria-busy="true" className={sectionClass}>
      <div className={headerClass}>
        <div className="mb-8 md:mb-10">
          <div className="product-skeleton__line h-9 w-64 max-w-full animate-pulse rounded-full sm:h-11" />
          <div className="product-skeleton__line mt-4 h-4 w-72 max-w-full animate-pulse rounded-full" />
        </div>
      </div>
      {[0, 1].map((row) => (
        <div key={row} className="mb-5 flex gap-5 overflow-hidden px-4">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="product-skeleton__line h-60 w-72 shrink-0 animate-pulse rounded-(--radius-card) sm:w-80" />
          ))}
        </div>
      ))}
    </section>
  );
}
