"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import Marquee from "react-fast-marquee";
import { FaStar } from "react-icons/fa";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";
const subscribeMotion = (onChange) => {
  const query = window.matchMedia(REDUCED_MOTION);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
};
const prefersReducedMotion = () => window.matchMedia(REDUCED_MOTION).matches;

function ReviewCard({ review, hidden }) {
  const photo = review.images?.[0]?.image;
  return (
    <article aria-hidden={hidden || undefined} className="testimonial-card mx-2.5 flex h-60 w-72 flex-col gap-3 overflow-hidden rounded-(--radius-card) p-5 sm:w-80 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <span className="flex gap-0.5" role="img" aria-label={`${review.rating} out of 5 stars`}>
          {[1, 2, 3, 4, 5].map((n) => (
            <FaStar key={n} className={`h-3.5 w-3.5 ${n <= review.rating ? "detail-star--on" : "detail-star--off"}`} aria-hidden="true" />
          ))}
        </span>
        {review.is_verified_purchase && <span className="review-verified shrink-0 rounded-full px-2 py-0.5 text-[0.6875rem] font-medium">Verified</span>}
      </div>
      <div className="flex min-h-0 flex-1 gap-3 overflow-hidden">
        <p className="testimonial-card__text line-clamp-4 self-start min-w-0 flex-1 text-sm leading-relaxed [overflow-wrap:anywhere]">
          {review.title && <span className="font-semibold">{review.title}. </span>}
          {review.text}
        </p>
        {photo && (
          // eslint-disable-next-line @next/next/no-img-element -- remote review photo at a fixed small size
          <img src={photo} alt="" loading="lazy" className="review-thumb h-16 w-16 shrink-0 rounded-lg object-cover" />
        )}
      </div>
      <div className="testimonial-card__footer mt-auto shrink-0 border-t pt-3">
        <p className="truncate text-sm font-semibold">{review.reviewer_name}</p>
        {review.product_name && (
          <Link href={`/products/${review.product_slug}`} tabIndex={hidden ? -1 : undefined} className="showcase-muted line-clamp-1 text-xs hover:underline">
            {review.product_name}
          </Link>
        )}
      </div>
    </article>
  );
}

// Two opposite-moving rows of approved reviews (react-fast-marquee, as BrandMarquee already uses). The reviews are
// split between the rows; with too few to fill a row, `autoFill` repeats that row's cards on screen (rendering only —
// no extra records), so the loop never shows a gap. Hover pauses; prefers-reduced-motion stops the motion entirely.
export default function ReviewMarquee({ reviews }) {
  const reduced = useSyncExternalStore(subscribeMotion, prefersReducedMotion, () => false);
  const half = Math.ceil(reviews.length / 2);
  // With a single review both rows show it; otherwise each row gets its own half.
  const rows = reviews.length > 1 ? [reviews.slice(0, half), reviews.slice(half)] : [reviews, reviews];

  return (
    <div className="brand-marquee__mask flex flex-col gap-5">
      {rows.map((row, index) => (
        <Marquee
          key={index}
          direction={index === 0 ? "right" : "left"} // row 1 moves left -> right, row 2 right -> left
          speed={28}
          play={!reduced}
          pauseOnHover
          gradient={false}
          autoFill
        >
          {row.map((review) => (
            <ReviewCard key={review.id} review={review} hidden={index === 1 && reviews.length === 1} />
          ))}
        </Marquee>
      ))}
    </div>
  );
}
