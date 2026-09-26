"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FaStar } from "react-icons/fa";
import { usePathname } from "next/navigation";
import { FiCheck, FiEdit2, FiEye, FiPlus, FiSearch, FiSlash, FiTrash2 } from "react-icons/fi";
import { ADMIN_BASE, staffBase } from "@/lib/staffPaths";
import { notify } from "@/lib/notify";
import { formatOrderDate, formatOrderDateTime } from "@/lib/orderStatus";
import { errorText } from "@/lib/productAdmin";
import ProductImage from "@/component/shared/ProductImage";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import Modal from "@/component/shared/Modal";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 10;
const SEARCH_DELAY_MS = 350;
// apps.reviews.models.ReviewStatus, exactly.
const STATUS_LABEL = { pending: "Pending", approved: "Approved", rejected: "Rejected" };
const TABS = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "", label: "All" },
];

async function reviewFetch(path, method = "GET") {
  try {
    const res = await fetch(`/api/admin/reviews${path}`, { method, cache: "no-store" });
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, data };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

function Stars({ value }) {
  return (
    <span className="flex gap-0.5" role="img" aria-label={`${value} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <FaStar key={n} className={`h-3.5 w-3.5 ${n <= value ? "detail-star--on" : "detail-star--off"}`} aria-hidden="true" />
      ))}
    </span>
  );
}

function StatusBadge({ status }) {
  return (
    <span className="review-status rounded-full px-2.5 py-1 text-xs font-medium" data-status={status}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

const customerOf = (r) => r.user?.full_name ?? r.reviewer_name;

function Actions({ review, busy, onView, onApprove, onReject, onDelete, showView = true, canEdit = false }) {
  return (
    <div className="flex items-center justify-end gap-1.5">
      {canEdit && (
        <Link
          href={`/dashboard/admin/reviews/${review.id}`}
          title="Edit review"
          aria-label="Edit review"
          className="icon-action flex h-9 w-9 items-center justify-center rounded-full"
        >
          <FiEdit2 className="h-4 w-4" aria-hidden="true" />
        </Link>
      )}
      {showView && (
      <button type="button" onClick={() => onView(review)} title="View review" aria-label="View review" className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
        <FiEye className="h-4 w-4" aria-hidden="true" />
      </button>
      )}
      {review.status !== "approved" && (
        <button
          type="button"
          onClick={() => onApprove(review)}
          disabled={busy}
          title="Approve review"
          aria-label="Approve review"
          className="icon-action icon-action--success flex h-9 w-9 items-center justify-center rounded-full disabled:opacity-50"
        >
          <FiCheck className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
      {review.status === "pending" && (
        <button
          type="button"
          onClick={() => onReject(review)}
          disabled={busy}
          title="Reject review"
          aria-label="Reject review"
          className="icon-action flex h-9 w-9 items-center justify-center rounded-full disabled:opacity-50"
        >
          <FiSlash className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
      <button
        type="button"
        onClick={() => onDelete(review)}
        disabled={busy}
        title="Delete review"
        aria-label="Delete review"
        className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full disabled:opacity-50"
      >
        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

// CCE Review Management over the EXISTING moderation API (apps.reviews.views_admin.AdminReviewViewSet, reached via
// app/api/admin/reviews; CCE may list, view, approve, reject and delete). Status is the backend's own
// pending/approved/rejected; filters are the ones that endpoint supports (status, rating, search over reviewer,
// text, product name/SKU and phone). Every change comes from the backend's response — nothing is changed locally
// first — and the proxy revalidates the public review data so the product page and homepage follow.
export default function CceReviewManagement({ initialReviews, initialCount }) {
  // Adding and editing reviews is Admin only (the backend's create/update are IsAdmin); CCE moderates.
  const isAdmin = staffBase(usePathname()) === ADMIN_BASE;
  const [reviews, setReviews] = useState(initialReviews);
  const [count, setCount] = useState(initialCount);
  const [status, setStatus] = useState("pending");
  const [rating, setRating] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [viewing, setViewing] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const requestId = useRef(0);
  const firstRender = useRef(true);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load({ nextStatus = status, nextRating = rating, nextSearch = search, nextPage = 1 } = {}) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
    if (nextStatus) params.set("status", nextStatus);
    if (nextRating) params.set("rating", nextRating);
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    const res = await reviewFetch(`?${params.toString()}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) {
      if (res.status === 404 && nextPage > 1) return load({ nextStatus, nextRating, nextSearch, nextPage: nextPage - 1 });
      notify.error(errorText(res, "Unable to load reviews. Please try again."));
      return;
    }
    setReviews(res.data.results ?? []);
    setCount(res.data.count ?? 0);
    setPage(nextPage);
  }

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = setTimeout(() => load({ nextSearch: search }), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  async function moderate(review, action) {
    if (busyId) return;
    setBusyId(review.id);
    const res = await reviewFetch(`/${review.id}/${action}`, "POST");
    setBusyId(null);
    if (!res.ok) {
      notify.error(errorText(res, `Unable to ${action} the review. Please try again.`));
      return;
    }
    notify.success(action === "approve" ? "Review approved successfully." : "Review rejected.");
    if (viewing?.id === review.id) setViewing(res.data);
    load({ nextPage: page }); // re-read: the review may have left the current tab
  }

  async function confirmDelete() {
    if (!pendingDelete || busyId) return;
    setBusyId(pendingDelete.id);
    const res = await reviewFetch(`/${pendingDelete.id}`, "DELETE");
    setBusyId(null);
    if (!res.ok) {
      notify.error(errorText(res, "Unable to delete the review. Please try again."));
      setPendingDelete(null);
      return;
    }
    notify.success("Review deleted successfully.");
    if (viewing?.id === pendingDelete.id) setViewing(null);
    setPendingDelete(null);
    load({ nextPage: page });
  }

  const actionProps = {
    canEdit: isAdmin,
    onView: setViewing,
    onApprove: (r) => moderate(r, "approve"),
    onReject: (r) => moderate(r, "reject"),
    onDelete: setPendingDelete,
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Review Management</h1>
        <p className="showcase-muted mt-1 text-sm">New customer reviews wait here as Pending. Approved reviews appear on the product page and count toward its rating.</p>
      </div>
        {isAdmin && (
          <Link href="/dashboard/admin/reviews/new" className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
            <FiPlus className="h-4 w-4" aria-hidden="true" />
            Add Review
          </Link>
        )}
      </div>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div role="tablist" aria-label="Review status" className="flex flex-wrap gap-1.5">
          {TABS.map((tab) => (
            <button
              key={tab.value || "all"}
              type="button"
              role="tab"
              aria-selected={status === tab.value}
              onClick={() => {
                if (tab.value === status) return;
                setStatus(tab.value);
                load({ nextStatus: tab.value });
              }}
              className={`auth-btn rounded-full px-4 py-2 text-xs font-medium ${status === tab.value ? "auth-btn--primary" : "auth-btn--outline"}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {/* A grid, not flex: .checkout-input is width:100%, so the grid (not a w-* class) sizes each control. */}
        <div className="grid min-w-0 flex-1 grid-cols-[minmax(0,1fr)_minmax(0,9.5rem)] gap-2">
          <div className="relative min-w-0">
            <label htmlFor="rv-search" className="sr-only">
              Search reviews
            </label>
            <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
            <input
              id="rv-search"
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search customer, product, SKU or text..."
              className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
            />
          </div>
          <label htmlFor="rv-rating" className="sr-only">
            Filter by rating
          </label>
          <select
            id="rv-rating"
            value={rating}
            onChange={(e) => {
              setRating(e.target.value);
              load({ nextRating: e.target.value });
            }}
            className="checkout-input rounded-lg px-3 py-2.5 text-sm"
          >
            <option value="">All ratings</option>
            {[5, 4, 3, 2, 1].map((n) => (
              <option key={n} value={n}>
                {n} star{n === 1 ? "" : "s"}
              </option>
            ))}
          </select>
        </div>
      </div>

      <p className="showcase-muted -mt-2 text-sm">
        {count} review{count === 1 ? "" : "s"}
      </p>

      {reviews.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-2 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">{loading ? "Loading..." : "No reviews found"}</p>
          {!loading && <p className="showcase-muted text-sm">{status === "pending" ? "Nothing is waiting for approval." : "Try a different filter or search."}</p>}
        </div>
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl lg:block">
            <table className="product-table w-full min-w-[900px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Product</th>
                  <th scope="col" className="px-4 py-3 font-medium">Customer</th>
                  <th scope="col" className="px-4 py-3 font-medium">Rating</th>
                  <th scope="col" className="px-4 py-3 font-medium">Review</th>
                  <th scope="col" className="px-4 py-3 font-medium">Status</th>
                  <th scope="col" className="px-4 py-3 font-medium">Date</th>
                  <th scope="col" className="px-4 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {reviews.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-3">
                      <div className="flex max-w-[14rem] items-center gap-3">
                        <div className="cart-thumb relative h-10 w-10 shrink-0 overflow-hidden rounded-lg">
                          <ProductImage src={r.product_detail?.feature_image} alt="" tight />
                        </div>
                        <span className="line-clamp-2 font-medium leading-snug">{r.product_detail?.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium">{customerOf(r)}</p>
                      {r.is_verified_purchase && <p className="showcase-muted text-xs">Verified purchase</p>}
                    </td>
                    <td className="px-4 py-3">
                      <Stars value={r.rating} />
                    </td>
                    <td className="max-w-[20rem] px-4 py-3">
                      {r.title && <p className="truncate font-medium">{r.title}</p>}
                      <p className="line-clamp-2 [overflow-wrap:anywhere]">{r.text}</p>
                      {r.images?.length > 0 && <p className="showcase-muted mt-1 text-xs">{r.images.length} photo{r.images.length === 1 ? "" : "s"}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs">{formatOrderDate(r.created_at)}</td>
                    <td className="px-4 py-3">
                      <Actions review={r} busy={busyId === r.id} {...actionProps} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 lg:hidden">
            {reviews.map((r) => (
              <li key={r.id} className="dashboard-card flex flex-col gap-3 rounded-2xl p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium leading-snug">{r.product_detail?.name}</p>
                    <p className="showcase-muted text-xs">
                      {customerOf(r)} · {formatOrderDate(r.created_at)}
                    </p>
                  </div>
                  <StatusBadge status={r.status} />
                </div>
                <Stars value={r.rating} />
                <p className="line-clamp-3 text-sm [overflow-wrap:anywhere]">{r.text}</p>
                <Actions review={r} busy={busyId === r.id} {...actionProps} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(next) => next !== page && load({ nextPage: next })} disabled={loading} />

      <Modal open={Boolean(viewing)} title="Review Details" onClose={() => setViewing(null)} wide>
        {viewing && (
          <div className="flex min-w-0 flex-col gap-4 text-sm">
            <div className="flex items-center gap-3">
              <div className="cart-thumb relative h-14 w-14 shrink-0 overflow-hidden rounded-lg">
                <ProductImage src={viewing.product_detail?.feature_image} alt="" tight />
              </div>
              <div className="min-w-0">
                {viewing.product_detail && (
                  <Link href={`/products/${viewing.product_detail.slug}`} target="_blank" className="font-medium hover:underline">
                    {viewing.product_detail.name}
                  </Link>
                )}
                <p className="showcase-muted text-xs">{viewing.product_detail?.sku}</p>
              </div>
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
              <dt className="showcase-muted">Customer</dt>
              <dd>
                {customerOf(viewing)}
                {viewing.is_verified_purchase && <span className="showcase-muted"> · Verified purchase</span>}
                {viewing.is_manual && <span className="showcase-muted"> · Added by staff</span>}
              </dd>
              <dt className="showcase-muted">Rating</dt>
              <dd>
                <Stars value={viewing.rating} />
              </dd>
              <dt className="showcase-muted">Status</dt>
              <dd>
                <StatusBadge status={viewing.status} />
              </dd>
              <dt className="showcase-muted">Date</dt>
              <dd>{formatOrderDateTime(viewing.created_at)}</dd>
            </dl>
            <div>
              {viewing.title && <p className="font-medium [overflow-wrap:anywhere]">{viewing.title}</p>}
              <p className="mt-1 whitespace-pre-line leading-relaxed [overflow-wrap:anywhere]">{viewing.text}</p>
            </div>
            {viewing.images?.length > 0 && (
              <div className="grid grid-cols-3 gap-2">
                {viewing.images.map((img) => (
                  <a key={img.id} href={img.image} target="_blank" rel="noreferrer" className="review-thumb block aspect-square overflow-hidden rounded-lg">
                    {/* eslint-disable-next-line @next/next/no-img-element -- remote review photos */}
                    <img src={img.image} alt="" className="h-full w-full object-cover" />
                  </a>
                ))}
              </div>
            )}
            {viewing.admin_reply && (
              <div className="review-reply rounded-xl px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-wide">Reply from GalPal</p>
                <p className="mt-1 [overflow-wrap:anywhere]">{viewing.admin_reply}</p>
              </div>
            )}
            <div className="flex justify-end border-t pt-4">
              <Actions review={viewing} busy={busyId === viewing.id} {...actionProps} showView={false} />
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Review?"
        description="Are you sure you want to delete this review? Its photos are removed too, and the product's rating is recalculated."
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={Boolean(pendingDelete) && busyId === pendingDelete.id}
        onConfirm={confirmDelete}
        onCancel={() => !busyId && setPendingDelete(null)}
      />
    </div>
  );
}
