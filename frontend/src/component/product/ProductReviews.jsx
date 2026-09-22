"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FaStar } from "react-icons/fa";
import { FiUpload, FiX } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import { useAuthed } from "@/lib/useAuthed";
import { REVIEWS_PAGE_SIZE } from "@/lib/reviewsData";

const STAR_LEVELS = [5, 4, 3, 2, 1];
const TEXT_MAX = 3000;
const MAX_IMAGES = 5; // matches the backend's CreateReviewSerializer limit

function Stars({ value, className = "h-4 w-4" }) {
  return (
    <span className="flex gap-0.5" role="img" aria-label={`${value} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <FaStar key={n} className={`${className} ${n <= value ? "detail-star--on" : "detail-star--off"}`} aria-hidden="true" />
      ))}
    </span>
  );
}

function formatDate(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function ReviewCard({ review }) {
  return (
    <article className="review-card flex flex-col gap-3 rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold">{review.reviewer_name}</h3>
          <div className="mt-2 flex items-center gap-2">
            <Stars value={review.rating} />
            {review.is_verified_purchase && <span className="review-verified rounded-full px-2 py-0.5 text-[0.6875rem] font-medium">Verified Purchase</span>}
          </div>
        </div>
        <time className="showcase-muted shrink-0 text-xs" dateTime={review.created_at}>
          {formatDate(review.created_at)}
        </time>
      </div>
      {review.title && <p className="text-sm font-medium">{review.title}</p>}
      <p className="text-sm leading-relaxed">{review.text}</p>
      {review.images?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {review.images.map((img) => (
            /* eslint-disable-next-line @next/next/no-img-element -- a handful of small review photos; not worth Image's overhead here */
            <img key={img.id} src={img.image} alt="" className="review-thumb h-16 w-16 rounded-lg object-cover" />
          ))}
        </div>
      )}
      {review.admin_reply && (
        <div className="review-reply rounded-xl px-4 py-3 text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide">Reply from GalPal</p>
          <p className="mt-1 leading-relaxed">{review.admin_reply}</p>
        </div>
      )}
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

// "Rating & Reviews", wired to the EXISTING reviews API: `product.slug` (GET /reviews/?product=, paginated —
// server-rendered first page in `initialReviews`, "Load more" fetches the rest) for the list, `breakdown` (GET
// /reviews/breakdown/) for the average/count/star bars, and POST /reviews/ (via /api/reviews) for a logged-in
// customer's own submission. The backend, not this component, decides which reviews are public: only APPROVED
// ones are ever returned, so a submitted review may not appear immediately — the success toast says so.
export default function ProductReviews({ product, initialReviews, breakdown }) {
  const router = useRouter();
  const authed = useAuthed();
  const [reviews, setReviews] = useState(initialReviews.results);
  const [hasMore, setHasMore] = useState(initialReviews.hasMore);
  const [page, setPage] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ rating: 0, text: "", images: [] });

  const average = Number(breakdown.average_rating) || 0;
  const total = breakdown.review_count ?? 0;
  const counts = breakdown.breakdown ?? {};

  async function loadMore() {
    setLoadingMore(true);
    try {
      const nextPage = page + 1;
      const res = await fetch(`/api/reviews?product=${encodeURIComponent(product.slug)}&page=${nextPage}&page_size=${REVIEWS_PAGE_SIZE}`, {
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to load more reviews. Please try again."));
        return;
      }
      setReviews((list) => [...list, ...(data.results ?? [])]);
      setHasMore(Boolean(data.next));
      setPage(nextPage);
    } catch {
      notify.error("Unable to load more reviews. Please try again.");
    } finally {
      setLoadingMore(false);
    }
  }

  function addImages(fileList) {
    const files = [...fileList].slice(0, MAX_IMAGES - form.images.length);
    if (files.length === 0) return;
    setForm((f) => ({ ...f, images: [...f.images, ...files].slice(0, MAX_IMAGES) }));
  }
  function removeImage(index) {
    setForm((f) => ({ ...f, images: f.images.filter((_, i) => i !== index) }));
  }

  async function submit(e) {
    e.preventDefault();
    if (submitting) return;
    if (!form.rating) return notify.error("Please select a star rating.");
    if (!form.text.trim()) return notify.error("Please write your review.");

    setSubmitting(true);
    try {
      const body = new FormData();
      body.set("product_id", String(product.id));
      body.set("rating", String(form.rating));
      body.set("text", form.text.trim());
      for (const file of form.images) body.append("images", file);

      const res = await fetch("/api/reviews", { method: "POST", body, cache: "no-store" });
      const data = await res.json().catch(() => null);

      if (!res.ok) {
        if (res.status === 401) {
          notify.error("Please login to submit a review.");
        } else if (res.status === 409) {
          notify.error(data?.error?.message || "You have already reviewed this product.");
        } else if (res.status === 403) {
          // e.g. "Only a customer account can write a review." (an admin/staff session) — the backend's own
          // eligibility rule, surfaced as-is rather than a generic failure message.
          notify.error(data?.error?.message || "You're not eligible to review this product.");
        } else {
          notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Failed to submit review."));
        }
        return;
      }

      notify.success("Review submitted successfully! It will appear once approved.");
      setForm({ rating: 0, text: "", images: [] });
      setFormOpen(false);
      router.refresh(); // picks up a pre-approved review (e.g. an already-verified customer) on the next server render
    } catch {
      notify.error("Failed to submit review.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section aria-labelledby="reviews-heading" className="detail-section mt-16 border-t pt-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="reviews-heading" className="custom-font text-2xl sm:text-3xl">
          Rating &amp; Reviews
        </h2>
        {authed ? (
          <button
            type="button"
            onClick={() => setFormOpen((open) => !open)}
            aria-expanded={formOpen}
            aria-controls="review-form"
            className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium"
          >
            {formOpen ? "Cancel" : "Write a Review"}
          </button>
        ) : (
          <Link href="/login" className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
            Login to Write a Review
          </Link>
        )}
      </div>

      {formOpen && authed && (
        <form id="review-form" onSubmit={submit} noValidate className="review-card mt-6 flex flex-col gap-4 rounded-2xl p-5 sm:p-6">
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">
              Your Rating <span aria-hidden="true">*</span>
            </span>
            <StarPicker value={form.rating} onChange={(rating) => setForm((f) => ({ ...f, rating }))} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="review-text" className="text-sm font-medium">
              Your Review <span aria-hidden="true">*</span>
            </label>
            <textarea
              id="review-text"
              name="text"
              rows={4}
              maxLength={TEXT_MAX}
              placeholder="Share your experience with this product"
              value={form.text}
              onChange={(e) => setForm((f) => ({ ...f, text: e.target.value }))}
              className="checkout-input resize-y rounded-lg px-3 py-2.5 text-sm"
            />
            <span className="showcase-muted self-end text-xs">
              {form.text.length}/{TEXT_MAX}
            </span>
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">
              Photos <span className="showcase-muted font-normal">(Optional, up to {MAX_IMAGES})</span>
            </span>
            <div className="flex flex-wrap gap-2">
              {form.images.map((file, i) => (
                <span key={`${file.name}-${i}`} className="review-thumb relative h-16 w-16 shrink-0 overflow-hidden rounded-lg">
                  {/* eslint-disable-next-line @next/next/no-img-element -- a local File preview, not a served asset */}
                  <img src={URL.createObjectURL(file)} alt="" className="h-full w-full object-cover" />
                  <button
                    type="button"
                    onClick={() => removeImage(i)}
                    aria-label="Remove photo"
                    className="review-thumb__remove absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full"
                  >
                    <FiX className="h-3 w-3" aria-hidden="true" />
                  </button>
                </span>
              ))}
              {form.images.length < MAX_IMAGES && (
                <label className="review-thumb-add flex h-16 w-16 shrink-0 cursor-pointer flex-col items-center justify-center gap-1 rounded-lg text-xs">
                  <FiUpload className="h-4 w-4" aria-hidden="true" />
                  Add
                  <input type="file" accept="image/*" multiple className="sr-only" onChange={(e) => addImages(e.target.files)} />
                </label>
              )}
            </div>
          </div>

          <button type="submit" disabled={submitting} className="auth-btn auth-btn--primary self-start rounded-full px-8 py-2.5 text-sm font-medium">
            {submitting ? "Submitting..." : "Submit Review"}
          </button>
        </form>
      )}

      <div className="mt-8 grid items-center gap-8 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:gap-12">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center lg:flex-col lg:items-stretch xl:flex-row xl:items-center">
          <div className="shrink-0">
            <p className="flex items-baseline gap-1.5">
              <span className="custom-font text-6xl leading-none sm:text-7xl">{average.toFixed(1)}</span>
              <span className="showcase-muted text-lg">/ 5</span>
            </p>
            <p className="showcase-muted mt-2 text-sm">
              ({total} {total === 1 ? "Review" : "Reviews"})
            </p>
          </div>

          <ul className="flex min-w-0 flex-1 flex-col gap-2.5" aria-label="Rating breakdown">
            {STAR_LEVELS.map((level) => {
              const n = counts[level] ?? counts[String(level)] ?? 0;
              return (
                <li key={level} className="flex items-center gap-3 text-sm">
                  <span className="flex w-9 shrink-0 items-center gap-1">
                    <FaStar className="detail-star--on h-3.5 w-3.5" aria-hidden="true" />
                    {level}
                  </span>
                  <span className="review-bar h-2 flex-1 overflow-hidden rounded-full" role="presentation">
                    <span className="review-bar__fill block h-full rounded-full" style={{ width: `${total ? (n / total) * 100 : 0}%` }} />
                  </span>
                  <span className="showcase-muted w-6 shrink-0 text-right text-xs">{n}</span>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="min-w-0">
          {reviews.length === 0 ? (
            <div className="review-card flex min-h-48 flex-col items-center justify-center gap-2 rounded-2xl px-6 py-10 text-center">
              <p className="custom-font text-xl">No reviews yet</p>
              <p className="showcase-muted text-sm">Be the first to share your thoughts on this product.</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {reviews.map((review) => (
                <ReviewCard key={review.id} review={review} />
              ))}
              {hasMore && (
                <button
                  type="button"
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="auth-btn auth-btn--outline self-center rounded-full px-6 py-2 text-sm font-medium"
                >
                  {loadingMore ? "Loading..." : "Load More Reviews"}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
