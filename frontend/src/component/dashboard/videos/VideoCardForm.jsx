"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FiFilm, FiUpload, FiX } from "react-icons/fi";
import { notify } from "@/lib/notify";
import formatPrice from "@/lib/formatPrice";
import { catalogFetch, errorText } from "@/lib/productAdmin";
import { VIDEO_ACCEPT, checkVideo, videoUpload } from "@/lib/videoAdmin";
import { useStaffHref } from "@/lib/staffPaths";
import { SingleImageInput } from "../products/ImageInputs";
import DualListPicker from "../coupons/DualListPicker";

const INPUT = "checkout-input rounded-lg px-3 py-2.5 text-sm";

function Section({ title, description, children }) {
  return (
    <section className="dashboard-card rounded-2xl p-5 sm:p-6">
      <h2 className="custom-font text-lg">{title}</h2>
      {description && <p className="showcase-muted mt-1 text-xs">{description}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function VideoPreview({ file, url }) {
  const objectUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => objectUrl && URL.revokeObjectURL(objectUrl), [objectUrl]);
  const src = objectUrl ?? url;
  if (!src) return null;
  return <video src={src} controls preload="metadata" className="video-preview aspect-video w-full max-w-sm rounded-xl" />;
}

// Add / Edit Video Card (Admin and CCE) over the EXISTING /admin/videos/ API (apps.videos). The backend's rules: a title,
// a thumbnail, and EXACTLY ONE video source — an uploaded MP4/WEBM (up to 50 MB) or an external link (e.g. YouTube);
// products are ids (many-to-many); lower sort order shows first; only active cards appear on the homepage. Files are
// sent only when a new one is picked, so an edit keeps the current video/thumbnail otherwise; a replaced file is removed
// from storage by the backend. Switching from an uploaded video to a link sends `remove_video_file`.
export default function VideoCardForm({ video = null, currencySymbol }) {
  const router = useRouter();
  const to = useStaffHref();
  const isEdit = Boolean(video);
  const fileRef = useRef(null);

  const [title, setTitle] = useState(video?.title ?? "");
  const [source, setSource] = useState(video && !video.video_file ? "url" : "file");
  const [videoFile, setVideoFile] = useState(null);
  const [externalUrl, setExternalUrl] = useState(video?.external_url ?? "");
  const [thumbnail, setThumbnail] = useState({ url: video?.thumbnail ?? null, file: null, removed: false });
  const [products, setProducts] = useState(() => (video?.products ?? []).map((p) => ({ id: p.id, label: p.name, hint: p.sku, image: p.feature_image })));
  const [sortOrder, setSortOrder] = useState(String(video?.sort_order ?? 0));
  const [isActive, setIsActive] = useState(video?.is_active ?? true);
  const [progress, setProgress] = useState(null); // upload %, while saving
  const [submitting, setSubmitting] = useState(false);

  const hasSavedFile = Boolean(video?.video_file);

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

  function pickVideo(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const problem = checkVideo(file);
    if (problem) return notify.error(problem);
    setVideoFile(file);
  }

  function validate() {
    if (!title.trim()) return "Title is required.";
    if (source === "file" && !videoFile && !hasSavedFile) return "Upload a video file, or switch to an external URL.";
    if (source === "url") {
      try {
        const u = new URL(externalUrl.trim());
        if (!["http:", "https:"].includes(u.protocol)) throw new Error();
      } catch {
        return "Enter a valid external URL starting with http:// or https://.";
      }
    }
    if (!thumbnail.file && !thumbnail.url) return "A thumbnail image is required.";
    if (!/^\d+$/.test(sortOrder.trim())) return "Sort order must be a whole number, 0 or more.";
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    const problem = validate();
    if (problem) return notify.error(problem);

    const fd = new FormData();
    fd.append("title", title.trim());
    fd.append("sort_order", sortOrder.trim());
    fd.append("is_active", String(isActive));
    if (source === "file") {
      if (videoFile) fd.append("video_file", videoFile);
      fd.append("external_url", ""); // exactly one source
    } else {
      fd.append("external_url", externalUrl.trim());
      if (hasSavedFile) fd.append("remove_video_file", "true");
    }
    if (thumbnail.file) fd.append("thumbnail", thumbnail.file);
    // Products: repeated ids; an explicit empty marker isn't possible in multipart, so a cleared list is sent after.
    for (const p of products) fd.append("product_ids", String(p.id));

    setSubmitting(true);
    setProgress(0);
    let res = await videoUpload(isEdit ? `/${video.id}` : "", isEdit ? "PATCH" : "POST", fd, setProgress);
    if (res.ok && products.length === 0 && isEdit && video.products.length > 0) {
      // multipart can't say "no products": clear them with a small JSON update
      res = await fetch(`/api/admin/videos/${video.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_ids: [] }),
      }).then(async (r) => ({ ok: r.ok, status: r.status, data: await r.json().catch(() => null) }));
    }
    setProgress(null);
    if (!res.ok) {
      setSubmitting(false);
      return notify.error(errorText(res, isEdit ? "Unable to update the video card." : "Unable to add the video card."));
    }
    notify.success(isEdit ? "Video card updated successfully." : "Video card added successfully.");
    router.push(to("/dashboard/CCE/video-cards"));
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <Section title="Video">
        <div className="flex flex-col gap-5">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="vf-title" className="text-sm font-medium">
              Title <span aria-hidden="true">*</span>
            </label>
            <input id="vf-title" type="text" maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} className={INPUT} placeholder="Morning Skincare Routine" />
          </div>

          <fieldset className="flex flex-col gap-3">
            <legend className="mb-2 text-sm font-medium">
              Video source <span aria-hidden="true">*</span>
            </legend>
            <div className="flex flex-wrap gap-4 text-sm">
              <label className="flex cursor-pointer items-center gap-2">
                <input type="radio" name="vf-source" checked={source === "file"} onChange={() => setSource("file")} className="form-check h-4 w-4" />
                Video file
              </label>
              <label className="flex cursor-pointer items-center gap-2">
                <input type="radio" name="vf-source" checked={source === "url"} onChange={() => setSource("url")} className="form-check h-4 w-4" />
                External URL
              </label>
            </div>
            <p className="showcase-muted text-xs">A card plays one or the other, never both.</p>

            {source === "file" ? (
              <div className="flex flex-col gap-3">
                <VideoPreview file={videoFile} url={!videoFile && hasSavedFile ? video.video_url : null} />
                <div className="flex flex-wrap items-center gap-3">
                  <input ref={fileRef} type="file" accept={VIDEO_ACCEPT} onChange={pickVideo} className="sr-only" aria-label="Video file" />
                  <button type="button" onClick={() => fileRef.current?.click()} className="auth-btn auth-btn--outline inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium">
                    <FiUpload className="h-3.5 w-3.5" aria-hidden="true" />
                    {videoFile || hasSavedFile ? "Replace video" : "Upload video"}
                  </button>
                  {videoFile && (
                    <span className="flex min-w-0 items-center gap-1.5 text-xs">
                      <FiFilm className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      <span className="truncate">{videoFile.name}</span>
                      <button type="button" onClick={() => setVideoFile(null)} aria-label="Remove chosen video" className="auth-error">
                        <FiX className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    </span>
                  )}
                  <span className="showcase-muted text-xs">MP4 or WEBM, up to 50 MB.</span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                <label htmlFor="vf-url" className="sr-only">
                  External URL
                </label>
                <input
                  id="vf-url"
                  type="url"
                  inputMode="url"
                  maxLength={500}
                  placeholder="https://example.com/video.mp4"
                  value={externalUrl}
                  onChange={(e) => setExternalUrl(e.target.value)}
                  className={INPUT}
                />
                {hasSavedFile && <p className="showcase-muted text-xs">Saving with a link removes the uploaded video file.</p>}
              </div>
            )}
          </fieldset>

          <SingleImageInput id="vf-thumb" label="Thumbnail" required value={thumbnail} onChange={setThumbnail} />
        </div>
      </Section>

      <Section title="Products" description="Shown as shoppable cards with the video. Only published products appear on the homepage.">
        <DualListPicker id="vf-products" label="Products" onSearch={searchProducts} chosen={products} onChange={setProducts} showImages allText="No products linked." />
      </Section>

      <Section title="Display">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="vf-sort" className="text-sm font-medium">
              Sort order
            </label>
            <input id="vf-sort" type="number" inputMode="numeric" min="0" step="1" value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} className={INPUT} />
            <p className="showcase-muted text-xs">Lower numbers show first; equal numbers show newest first.</p>
          </div>
          <label htmlFor="vf-active" className="flex cursor-pointer items-start gap-2.5 self-center text-sm">
            <input id="vf-active" type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="form-check mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Is active
              <span className="showcase-muted block text-xs">Only active cards appear in the homepage&apos;s shoppable videos.</span>
            </span>
          </label>
        </div>
      </Section>

      {progress !== null && (
        <div className="flex flex-col gap-1.5" role="status" aria-live="polite">
          <div className="upload-progress h-2 w-full overflow-hidden rounded-full">
            <div className="upload-progress__bar h-full rounded-full" style={{ width: `${progress}%` }} />
          </div>
          <p className="showcase-muted text-xs">{progress < 100 ? `Uploading... ${progress}%` : "Saving..."}</p>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Link href={to("/dashboard/CCE/video-cards")} className="auth-btn auth-btn--outline rounded-full px-6 py-2.5 text-sm font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={submitting} aria-busy={submitting} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {submitting ? (isEdit ? "Saving..." : "Adding...") : isEdit ? "Save Changes" : "Add Video Card"}
        </button>
      </div>
    </form>
  );
}
