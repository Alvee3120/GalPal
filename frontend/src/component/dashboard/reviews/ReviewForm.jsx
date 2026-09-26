"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FaStar } from "react-icons/fa";
import { FiUpload, FiX } from "react-icons/fi";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { catalogFetch, errorText } from "@/lib/productAdmin";
import { USER_ROLE_LABEL, userFetch } from "@/lib/userAdmin";
import { checkImage } from "../products/ImageInputs";
import SearchPicker from "../SearchPicker";

const INPUT = "checkout-input rounded-lg px-3 py-2.5 text-sm";
const TEXT_MAX = 3000; // apps.reviews.models.Review.text
const MAX_IMAGES = 5; // ManualReviewSerializer.images
// apps.reviews.models.ReviewStatus, exactly.
const STATUSES = [
  { value: "approved", label: "Approved" },
  { value: "pending", label: "Pending" },
  { value: "rejected", label: "Rejected" },
];

function StarPicker({ value, onChange }) {
  const [hover, setHover] = useState(0);
  const shown = hover || value;
  return (
    <div role="radiogroup" aria-label="Rating" className="flex gap-1" onMouseLeave={() => setHover(0)}>
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

function PhotoPreviews({ files, onRemove }) {
  const urls = useMemo(() => files.map((file) => URL.createObjectURL(file)), [files]);
  useEffect(() => () => urls.forEach((url) => URL.revokeObjectURL(url)), [urls]);
  return files.map((file, i) => (
    <span key={`${file.name}-${i}`} className="review-thumb relative h-16 w-16 shrink-0 overflow-hidden rounded-lg">
      {/* eslint-disable-next-line @next/next/no-img-element -- a local File preview */}
      <img src={urls[i]} alt="" className="h-full w-full object-cover" />
      <button type="button" onClick={() => onRemove(i)} aria-label="Remove photo" className="review-thumb__remove absolute right-0.5 top-0.5 flex h-5 w-5 items-center justify-center rounded-full">
        <FiX className="h-3 w-3" aria-hidden="true" />
      </button>
    </span>
  ));
}

// Admin Add / Edit Review over the EXISTING review API: POST /admin/reviews/ (the manual-review create, now able to name
// a real account with `user_id`) and PATCH /admin/reviews/<id>/ — both Admin only backend-side. The review is an
// ordinary Review row (the customer is optional — without one it's a testimonial under a typed name, as the
// backend's manual review allows): once Approved it shows on the product page and the homepage marquee and counts toward the
// product's rating (recomputed by the backend's review signal), exactly like a customer's own review. One review per
// product per account is still enforced; the backend's message is shown if it refuses. On Edit the product and
// reviewer are fixed (the backend doesn't move a review between products/accounts); rating, title, text and status
// can change. Photos can be added when creating (the edit API doesn't change photos).
export default function ReviewForm({ review = null, currencySymbol }) {
  const router = useRouter();
  const isEdit = Boolean(review);
  const [product, setProduct] = useState(
    review?.product_detail ? { id: review.product_detail.id, label: review.product_detail.name, hint: review.product_detail.sku, image: review.product_detail.feature_image } : null,
  );
  const [reviewer, setReviewer] = useState(
    review ? { id: review.user?.id ?? null, label: review.user?.full_name ?? review.reviewer_name, hint: review.user ? "" : "Testimonial (no account)" } : null,
  );
  const [reviewerName, setReviewerName] = useState(""); // used only when no customer account is chosen
  const [rating, setRating] = useState(review?.rating ?? 0);
  const [title, setTitle] = useState(review?.title ?? "");
  const [text, setText] = useState(review?.text ?? "");
  const [status, setStatus] = useState(review?.status ?? "approved");
  const [images, setImages] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  const searchProducts = useCallback(
    async (query) => {
      const params = new URLSearchParams({ page_size: "20" });
      if (query) params.set("search", query);
      const res = await catalogFetch(`products?${params.toString()}`);
      return res.ok
        ? (res.data.results ?? []).map((p) => ({ id: p.id, label: p.name, hint: `${p.sku} · ${formatPrice(p.effective_price ?? p.regular_price, currencySymbol)}`, image: p.feature_image }))
        : [];
    },
    [currencySymbol],
  );

  const searchUsers = useCallback(async (query) => {
    const params = new URLSearchParams({ page_size: "20" });
    if (query) params.set("search", query);
    const res = await userFetch(`?${params.toString()}`);
    return res.ok
      ? (res.data.results ?? []).map((u) => ({ id: u.id, label: u.full_name || u.phone, hint: [u.phone, u.email, USER_ROLE_LABEL[u.role]].filter(Boolean).join(" · ") }))
      : [];
  }, []);

  function addImages(fileList) {
    const good = [];
    for (const file of [...fileList]) {
      const problem = checkImage(file);
      if (problem) notify.error(`${file.name}: ${problem}`);
      else good.push(file);
    }
    setImages((list) => [...list, ...good].slice(0, MAX_IMAGES));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    if (!product) return notify.error("Please choose a product.");
    if (!rating) return notify.error("Please select a star rating.");
    if (!text.trim()) return notify.error("Please write the review.");

    let body;
    if (isEdit) {
      body = { rating, title: title.trim(), text: text.trim(), status };
    } else {
      body = new FormData();
      body.append("product_id", String(product.id));
      // A chosen customer's account, or else a testimonial under a typed name ("Anonymous" when left empty).
      if (reviewer) body.append("user_id", String(reviewer.id));
      else body.append("reviewer_name", reviewerName.trim() || "Anonymous");
      body.append("rating", String(rating));
      body.append("title", title.trim());
      body.append("text", text.trim());
      body.append("status", status);
      for (const file of images) body.append("images", file);
    }

    setSubmitting(true);
    try {
      const res = await fetch(`/api/admin/reviews${isEdit ? `/${review.id}` : ""}`, {
        method: isEdit ? "PATCH" : "POST",
        body: isEdit ? JSON.stringify(body) : body,
        headers: isEdit ? { "Content-Type": "application/json" } : undefined,
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setSubmitting(false);
        return notify.error(errorText({ ok: false, status: res.status, data }, isEdit ? "Unable to update the review." : "Unable to add the review."));
      }
    } catch {
      setSubmitting(false);
      return notify.error("We couldn't reach the server. Please try again.");
    }
    notify.success(isEdit ? "Review updated successfully." : "Review added successfully.");
    router.push("/dashboard/admin/reviews");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <section className="dashboard-card rounded-2xl p-5 sm:p-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <SearchPicker
            id="rf-product"
            label="Product"
            placeholder="Search products by name or SKU..."
            search={searchProducts}
            value={product}
            onChange={setProduct}
            showImages
            required
            disabled={isEdit}
          />
          <div className="flex min-w-0 flex-col gap-3">
            <SearchPicker
              id="rf-user"
              label="Customer (Optional)"
              placeholder="Search by name, phone or email..."
              search={searchUsers}
              value={reviewer}
              onChange={setReviewer}
              disabled={isEdit}
            />
            {!isEdit && !reviewer && (
              <div className="flex min-w-0 flex-col gap-1.5">
                <label htmlFor="rf-name" className="text-sm font-medium">
                  Reviewer name <span className="showcase-muted font-normal">(Optional)</span>
                </label>
                <input
                  id="rf-name"
                  type="text"
                  maxLength={150}
                  placeholder="Anonymous"
                  value={reviewerName}
                  onChange={(e) => setReviewerName(e.target.value)}
                  className={INPUT}
                />
                <p className="showcase-muted text-xs">No customer chosen: the review shows under this name (Anonymous if empty), with no account linked.</p>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">
              Rating <span aria-hidden="true">*</span>
            </span>
            <StarPicker value={rating} onChange={setRating} />
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="rf-status" className="text-sm font-medium">
              Status
            </label>
            <select id="rf-status" value={status} onChange={(e) => setStatus(e.target.value)} className={INPUT}>
              {STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            <p className="showcase-muted text-xs">Only Approved reviews show on the product page and homepage, and count toward the rating.</p>
          </div>

          <div className="flex min-w-0 flex-col gap-1.5 md:col-span-2">
            <label htmlFor="rf-title" className="text-sm font-medium">
              Title <span className="showcase-muted font-normal">(Optional)</span>
            </label>
            <input id="rf-title" type="text" maxLength={150} value={title} onChange={(e) => setTitle(e.target.value)} className={INPUT} />
          </div>
          <div className="flex min-w-0 flex-col gap-1.5 md:col-span-2">
            <label htmlFor="rf-text" className="text-sm font-medium">
              Review <span aria-hidden="true">*</span>
            </label>
            <textarea id="rf-text" rows={5} maxLength={TEXT_MAX} placeholder="Write review..." value={text} onChange={(e) => setText(e.target.value)} className={`${INPUT} resize-y`} />
            <span className="showcase-muted self-end text-xs">
              {text.length}/{TEXT_MAX}
            </span>
          </div>

          {!isEdit && (
            <div className="flex flex-col gap-1.5 md:col-span-2">
              <span className="text-sm font-medium">
                Photos <span className="showcase-muted font-normal">(Optional, up to {MAX_IMAGES})</span>
              </span>
              <div className="flex flex-wrap gap-2">
                <PhotoPreviews files={images} onRemove={(i) => setImages((list) => list.filter((_, idx) => idx !== i))} />
                {images.length < MAX_IMAGES && (
                  <label className="review-thumb-add flex h-16 w-16 shrink-0 cursor-pointer flex-col items-center justify-center gap-1 rounded-lg text-xs">
                    <FiUpload className="h-4 w-4" aria-hidden="true" />
                    Add
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      multiple
                      className="sr-only"
                      onChange={(e) => {
                        addImages(e.target.files ?? []);
                        e.target.value = "";
                      }}
                    />
                  </label>
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Link href="/dashboard/admin/reviews" className="auth-btn auth-btn--outline rounded-full px-6 py-2.5 text-sm font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={submitting} aria-busy={submitting} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {submitting ? (isEdit ? "Saving Review..." : "Adding Review...") : isEdit ? "Save Changes" : "Add Review"}
        </button>
      </div>
    </form>
  );
}
