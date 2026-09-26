"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { FiEdit2, FiPlus, FiSearch, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { videoFetch } from "@/lib/videoAdmin";
import { useStaffHref } from "@/lib/staffPaths";
import ProductImage from "@/component/shared/ProductImage";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import DashboardPagination from "../DashboardPagination";

const PAGE_SIZE = 10;
const SEARCH_DELAY_MS = 350;

function ActiveBadge({ active }) {
  return (
    <span className="product-status-badge rounded-full px-2.5 py-1 text-xs font-medium" data-status={active ? "active" : "inactive"}>
      {active ? "Active" : "Inactive"}
    </span>
  );
}

function Thumb({ src }) {
  return (
    <div className="cart-thumb relative aspect-video w-24 shrink-0 overflow-hidden rounded-lg">
      <ProductImage src={src} alt="" bleed />
    </div>
  );
}

// Video Cards (Admin and CCE) over the EXISTING /admin/videos/ API (apps.videos — IsCatalogStaff). Search by title and
// pagination run on the server; the list is in the storefront's display order (sort order, then newest). The homepage's
// shoppable videos show the active cards in that same order.
export default function VideoCardManagement({ initialVideos, initialCount }) {
  const to = useStaffHref();
  const [videos, setVideos] = useState(initialVideos);
  const [count, setCount] = useState(initialCount);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const requestId = useRef(0);
  const firstRender = useRef(true);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  async function load(nextSearch = search, nextPage = 1) {
    const id = ++requestId.current;
    setLoading(true);
    const params = new URLSearchParams({ page_size: String(PAGE_SIZE), page: String(nextPage) });
    if (nextSearch.trim()) params.set("search", nextSearch.trim());
    const res = await videoFetch(`?${params.toString()}`);
    if (id !== requestId.current) return;
    setLoading(false);
    if (!res.ok) {
      if (res.status === 404 && nextPage > 1) return load(nextSearch, nextPage - 1);
      notify.error(errorText(res, "Unable to load video cards. Please try again."));
      return;
    }
    setVideos(res.data.results ?? []);
    setCount(res.data.count ?? 0);
    setPage(nextPage);
  }

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = setTimeout(() => load(search, 1), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  async function confirmDelete() {
    if (!pendingDelete || deleting) return;
    setDeleting(true);
    const res = await videoFetch(`/${pendingDelete.id}`, { method: "DELETE" });
    setDeleting(false);
    setPendingDelete(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the video card. Please try again."));
    notify.success("Video card deleted successfully.");
    load(search, page);
  }

  const edit = (v) => to(`/dashboard/CCE/video-cards/${v.id}`);
  const addLink = (
    <Link href={to("/dashboard/CCE/video-cards/new")} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium">
      <FiPlus className="h-4 w-4" aria-hidden="true" />
      Add Video Card
    </Link>
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="custom-font text-2xl sm:text-3xl">Video Cards</h1>
          <p className="showcase-muted mt-1 text-sm">
            {count} video card{count === 1 ? "" : "s"} · shown on the homepage in sort order
          </p>
        </div>
        {addLink}
      </div>

      <div className="relative">
        <label htmlFor="vc-search" className="sr-only">
          Search video cards
        </label>
        <FiSearch className="showcase-muted pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2" aria-hidden="true" />
        <input
          id="vc-search"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search video cards..."
          className="checkout-input w-full rounded-lg py-2.5 pl-9 pr-3 text-sm"
        />
      </div>

      {videos.length === 0 ? (
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-xl">{loading ? "Loading..." : "No video cards found."}</p>
          {!loading && !search.trim() && addLink}
        </div>
      ) : (
        <div className={`transition-opacity ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
          <div className="dashboard-card hidden overflow-x-auto rounded-2xl md:block">
            <table className="product-table w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr>
                  <th scope="col" className="px-4 py-3 font-medium">Thumbnail</th>
                  <th scope="col" className="px-4 py-3 font-medium">Title</th>
                  <th scope="col" className="px-4 py-3 font-medium">Is Active</th>
                  <th scope="col" className="px-4 py-3 font-medium">Edit</th>
                  <th scope="col" className="px-4 py-3 font-medium">Delete</th>
                </tr>
              </thead>
              <tbody>
                {videos.map((v) => (
                  <tr key={v.id}>
                    <td className="px-4 py-3">
                      <Thumb src={v.thumbnail} />
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-medium">{v.title}</p>
                      <p className="showcase-muted text-xs">
                        {v.video_file ? "Uploaded video" : "External link"} · {v.products.length} product{v.products.length === 1 ? "" : "s"} · order {v.sort_order}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <ActiveBadge active={v.is_active} />
                    </td>
                    <td className="px-4 py-3">
                      <Link href={edit(v)} title="Edit video card" aria-label={`Edit video card ${v.title}`} className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                        <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setPendingDelete(v)}
                        title="Delete video card"
                        aria-label={`Delete video card ${v.title}`}
                        className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full"
                      >
                        <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="flex flex-col gap-3 md:hidden">
            {videos.map((v) => (
              <li key={v.id} className="dashboard-card flex items-center gap-3 rounded-2xl p-3">
                <Thumb src={v.thumbnail} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{v.title}</p>
                  <div className="mt-1.5">
                    <ActiveBadge active={v.is_active} />
                  </div>
                </div>
                <div className="flex shrink-0 flex-col gap-1.5">
                  <Link href={edit(v)} title="Edit video card" aria-label={`Edit video card ${v.title}`} className="icon-action flex h-9 w-9 items-center justify-center rounded-full">
                    <FiEdit2 className="h-4 w-4" aria-hidden="true" />
                  </Link>
                  <button
                    type="button"
                    onClick={() => setPendingDelete(v)}
                    title="Delete video card"
                    aria-label={`Delete video card ${v.title}`}
                    className="icon-action icon-action--danger flex h-9 w-9 items-center justify-center rounded-full"
                  >
                    <FiTrash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <DashboardPagination page={page} totalPages={totalPages} onPageChange={(next) => next !== page && load(search, next)} disabled={loading} />

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Video Card?"
        description={pendingDelete ? `Are you sure you want to delete this video card? "${pendingDelete.title}" and its uploaded files will be removed.` : ""}
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}
