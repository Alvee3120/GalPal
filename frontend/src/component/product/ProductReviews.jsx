"use client";

import { useEffect, useRef, useState } from "react";
import { FaStar } from "react-icons/fa";
import { FiChevronLeft, FiChevronRight } from "react-icons/fi";
import { notify } from "@/lib/notify";

const STAR_LEVELS = [5, 4, 3, 2, 1];
const NAME_MAX = 60;
const COMMENT_MAX = 500;

function Stars({ value, className = "h-4 w-4" }) {
  return (
    <span className="flex gap-0.5" role="img" aria-label={`${value} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <FaStar key={n} className={`${className} ${n <= value ? "detail-star--on" : "detail-star--off"}`} aria-hidden="true" />
      ))}
    </span>
  );
}

function ReviewCard({ review }) {
  return (
    <article className="review-card flex h-full w-full shrink-0 snap-center flex-col gap-3 rounded-2xl p-5 sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold">{review.name}</h3>
          <div className="mt-2">
            <Stars value={review.rating} />
          </div>
        </div>
        <time className="showcase-muted shrink-0 text-xs">{review.date}</time>
      </div>
      <p className="text-sm leading-relaxed">&ldquo;{review.comment}&rdquo;</p>
      <span className="review-avatar mt-auto flex h-12 w-12 items-center justify-center rounded-full text-lg font-semibold" aria-hidden="true">
        {review.name.trim().charAt(0).toUpperCase()}
      </span>
    </article>
  );
}

function StarPicker({ value, onChange }) {
  const [hover, setHover] = useState(0);
  const shown = hover || value;
  return (
    <div role="radiogroup" aria-label="Your rating" className="flex gap-1" onMouseLeave={() => setHover(0)}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} ${n === 1 ? "star" : "stars"}`}
          onClick={() => onChange(n)}
          onMouseEnter={() => setHover(n)}
          className="review-star-btn rounded p-0.5"
        >
          <FaStar className={`h-7 w-7 ${n <= shown ? "detail-star--on" : "detail-star--off"}`} aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}

// "Rating & Reviews": average + star breakdown on the left, a sliding review carousel on the right, and a Write a Review
// form. The backend has no reviews API yet (it only stores the average_rating / review_count numbers), so reviews added
// here live in this component's state: they update the list, the average and the counter immediately, but are not saved
// and are gone on refresh. The product's existing average/count (0 on every current product) is folded into the totals.
export default function ProductReviews({ product }) {
  const [reviews, setReviews] = useState([]);
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({ rating: 0, name: "", comment: "" });
  const [slide, setSlide] = useState(0);
  const scrollerRef = useRef(null);

  // A new review is added in FRONT; browsers keep snap-scrolled content in view when that happens, which would land on
  // the older review. Jump back to the newest one once the list has re-rendered.
  useEffect(() => {
    scrollerRef.current?.scrollTo({ left: 0, behavior: "instant" });
  }, [reviews.length]);

  const baseCount = Number(product.review_count) || 0;
  const baseAverage = Number(product.average_rating) || 0;
  const total = baseCount + reviews.length;
  const average = total ? (baseAverage * baseCount + reviews.reduce((sum, r) => sum + r.rating, 0)) / total : 0;
  const perLevel = (level) => reviews.filter((r) => r.rating === level).length;

  function submit(e) {
    e.preventDefault();
    if (!form.rating) return notify.error("Please select a star rating.");
    if (!form.name.trim()) return notify.error("Please enter your name.");
    if (!form.comment.trim()) return notify.error("Please write your review.");
    setReviews((list) => [
      {
        id: Date.now(),
        name: form.name.trim(),
        rating: form.rating,
        comment: form.comment.trim(),
        date: new Date().toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }),
      },
      ...list,
    ]);
    setForm({ rating: 0, name: "", comment: "" });
    setFormOpen(false);
    setSlide(0);
    notify.success("Thanks for your review!");
  }

  const scrollBy = (direction) => {
    const el = scrollerRef.current;
    if (el) el.scrollBy({ left: direction * el.clientWidth, behavior: "smooth" });
  };
  const onScroll = (e) => {
    const el = e.currentTarget;
    setSlide(Math.round(el.scrollLeft / Math.max(1, el.clientWidth)));
  };

  const set = (name) => (e) => setForm((f) => ({ ...f, [name]: e.target.value }));

  return (
    <section aria-labelledby="reviews-heading" className="detail-section mt-16 border-t pt-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="reviews-heading" className="custom-font text-2xl sm:text-3xl">
          Rating &amp; Reviews
        </h2>
        <button
          type="button"
          onClick={() => setFormOpen((open) => !open)}
          aria-expanded={formOpen}
          aria-controls="review-form"
          className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium"
        >
          {formOpen ? "Cancel" : "Write a Review"}
        </button>
      </div>

      {formOpen && (
        <form id="review-form" onSubmit={submit} noValidate className="review-card mt-6 flex flex-col gap-4 rounded-2xl p-5 sm:p-6">
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">
              Your Rating <span aria-hidden="true">*</span>
            </span>
            <StarPicker value={form.rating} onChange={(rating) => setForm((f) => ({ ...f, rating }))} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="review-name" className="text-sm font-medium">
              Name <span aria-hidden="true">*</span>
            </label>
            <input id="review-name" name="name" type="text" autoComplete="name" maxLength={NAME_MAX} placeholder="Enter your name" value={form.name} onChange={set("name")} className="checkout-input rounded-lg px-3 py-2.5 text-sm" />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="review-comment" className="text-sm font-medium">
              Your Review <span aria-hidden="true">*</span>
            </label>
            <textarea id="review-comment" name="comment" rows={4} maxLength={COMMENT_MAX} placeholder="Share your experience with this product" value={form.comment} onChange={set("comment")} className="checkout-input resize-y rounded-lg px-3 py-2.5 text-sm" />
            <span className="showcase-muted self-end text-xs">
              {form.comment.length}/{COMMENT_MAX}
            </span>
          </div>
          <button type="submit" className="auth-btn auth-btn--primary self-start rounded-full px-8 py-2.5 text-sm font-medium">
            Submit Review
          </button>
        </form>
      )}

      <div className="mt-8 grid items-center gap-8 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:gap-12">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center lg:flex-col lg:items-stretch xl:flex-row xl:items-center">
          <div className="shrink-0">
            <p className="flex items-baseline gap-1.5">
              <span className="custom-font text-6xl leading-none sm:text-7xl" data-testid="review-average">
                {average.toFixed(1)}
              </span>
              <span className="showcase-muted text-lg">/ 5</span>
            </p>
            <p className="showcase-muted mt-2 text-sm" data-testid="review-count">
              ({total} {total === 1 ? "Review" : "Reviews"})
            </p>
          </div>

          <ul className="flex min-w-0 flex-1 flex-col gap-2.5" aria-label="Rating breakdown">
            {STAR_LEVELS.map((level) => (
              <li key={level} className="flex items-center gap-3 text-sm">
                <span className="flex w-9 shrink-0 items-center gap-1">
                  <FaStar className="detail-star--on h-3.5 w-3.5" aria-hidden="true" />
                  {level}
                </span>
                <span className="review-bar h-2 flex-1 overflow-hidden rounded-full" role="presentation">
                  <span className="review-bar__fill block h-full rounded-full" style={{ width: `${reviews.length ? (perLevel(level) / reviews.length) * 100 : 0}%` }} />
                </span>
                <span className="showcase-muted w-6 shrink-0 text-right text-xs">{perLevel(level)}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="min-w-0">
          {reviews.length === 0 ? (
            <div className="review-card flex min-h-48 flex-col items-center justify-center gap-2 rounded-2xl px-6 py-10 text-center">
              <p className="custom-font text-xl">No reviews yet</p>
              <p className="showcase-muted text-sm">Be the first to share your thoughts on this product.</p>
            </div>
          ) : (
            <>
              <div className="relative">
                <div
                  ref={scrollerRef}
                  onScroll={onScroll}
                  className="flex snap-x snap-mandatory overflow-x-auto scroll-smooth [overflow-anchor:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
                  aria-live="polite"
                >
                  {reviews.map((review) => (
                    <div key={review.id} className="w-full shrink-0 snap-center px-0.5 py-1">
                      <ReviewCard review={review} />
                    </div>
                  ))}
                </div>
                {reviews.length > 1 && (
                  <>
                    <button type="button" onClick={() => scrollBy(-1)} disabled={slide === 0} aria-label="Previous review" className="review-nav absolute left-1 top-1/2 sm:-left-3 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full">
                      <FiChevronLeft className="h-5 w-5" aria-hidden="true" />
                    </button>
                    <button type="button" onClick={() => scrollBy(1)} disabled={slide >= reviews.length - 1} aria-label="Next review" className="review-nav absolute right-1 top-1/2 sm:-right-3 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full">
                      <FiChevronRight className="h-5 w-5" aria-hidden="true" />
                    </button>
                  </>
                )}
              </div>
              {reviews.length > 1 && (
                <div className="review-bar mx-auto mt-4 h-1 w-40 overflow-hidden rounded-full" role="presentation">
                  <span className="review-bar__fill block h-full rounded-full transition-[margin,width] duration-300" style={{ width: `${100 / reviews.length}%`, marginLeft: `${(slide * 100) / reviews.length}%` }} />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
