"use client";

import { useState } from "react";
import { FiAlertCircle, FiArrowDown, FiArrowUp, FiEdit2, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import Modal from "@/component/shared/Modal";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import { SingleImageInput } from "@/component/dashboard/products/ImageInputs";
import ImageDropzone from "./ImageDropzone";

export const MAX_BANNERS = 3; // the backend enforces the same cap (apps.banners.services.MAX_BANNERS)

async function bannerRequest(path, { method = "GET", body } = {}) {
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  try {
    const r = await fetch(`/api/admin/hero-banners${path}`, {
      method,
      cache: "no-store",
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
      headers: body === undefined || isForm ? undefined : { "Content-Type": "application/json" },
    });
    return { ok: r.ok, status: r.status, data: r.status === 204 ? null : await r.json().catch(() => null) };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

const byOrder = (list) => list.filter(Boolean).sort((a, b) => a.sort_order - b.sort_order || a.id - b.id);

// Admin → Hero Banners: up to 3 homepage hero banners over the EXISTING apps.banners admin API. Each has a desktop
// image (required) and an optional mobile image (tablet keeps falling back to desktop), alt text, active/inactive
// and a display order. Only active banners show on the homepage, in this order; one active banner is a static image,
// 2–3 slide. Changes revalidate the homepage (app/api/admin/hero-banners).
export default function HeroBannerManagement({ initialBanners }) {
  const [banners, setBanners] = useState(() => byOrder(initialBanners ?? []));
  const [editing, setEditing] = useState(null); // null | "new" | banner
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [uploading, setUploading] = useState(false);

  if (!initialBanners) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="custom-font text-2xl sm:text-3xl">Hero Banners</h1>
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <FiAlertCircle className="h-8 w-8" aria-hidden="true" />
          <p className="text-sm">Unable to load the hero banners. Please refresh the page.</p>
        </div>
      </div>
    );
  }

  const full = banners.length >= MAX_BANNERS;

  function saved(banner) {
    if (!banner?.id) return;
    setBanners((list) => byOrder(list.some((b) => b.id === banner.id) ? list.map((b) => (b.id === banner.id ? banner : b)) : [...list, banner]));
  }

  // An empty slot's drop zone: the image becomes a new, active banner at the end of the order.
  async function uploadNew(file) {
    const fd = new FormData();
    fd.append("desktop_image", file);
    fd.append("title", `Hero banner ${banners.length + 1}`); // internal label only
    fd.append("is_active", "true");
    fd.append("sort_order", String(banners.length ? Math.max(...banners.map((b) => b.sort_order)) + 1 : 0));
    setUploading(true);
    const res = await bannerRequest("", { method: "POST", body: fd });
    setUploading(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to upload the banner."));
    saved(res.data);
    notify.success("Banner uploaded. Use Edit to add a mobile image or alt text.");
  }

  async function toggleActive(banner) {
    setBusyId(banner.id);
    const res = await bannerRequest(`/${banner.id}`, { method: "PATCH", body: { is_active: !banner.is_active } });
    setBusyId(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to update the banner."));
    saved(res.data);
    notify.success(res.data?.is_active ? "Banner activated." : "Banner deactivated.");
  }

  async function move(index, step) {
    const order = banners.map((b) => b.id);
    [order[index], order[index + step]] = [order[index + step], order[index]];
    setBusyId(banners[index].id);
    const res = await bannerRequest("/reorder", { method: "POST", body: order });
    setBusyId(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to change the order."));
    setBanners(byOrder(Array.isArray(res.data) ? res.data : banners));
    notify.success("Banner order updated.");
  }

  async function confirmDelete() {
    const target = pendingDelete; // captured now: the state is cleared below, before React applies the list update
    if (!target || deleting) return;
    setDeleting(true);
    const res = await bannerRequest(`/${target.id}`, { method: "DELETE" });
    setDeleting(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the banner."));
    setBanners((list) => list.filter((b) => b && b.id !== target.id));
    setPendingDelete(null);
    notify.success("Banner deleted.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Hero Banners</h1>
        <p className="showcase-muted text-sm">Upload up to {MAX_BANNERS} banner images · {banners.length} of {MAX_BANNERS} used</p>
        {full && <p className="showcase-muted mt-1 text-xs">Maximum {MAX_BANNERS} banners allowed. Delete one to upload another.</p>}
        {banners.length === 0 && (
          <p className="showcase-muted mt-1 text-xs">No banners yet — the homepage shows its default banner until you upload one.</p>
        )}
      </div>

      <ul className="flex flex-col gap-4 lg:flex-row lg:items-stretch">
        {banners.map((banner, index) => (
          <li key={banner.id} className="dashboard-card flex min-w-0 flex-1 flex-col gap-4 rounded-2xl p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="custom-font text-lg font-bold">Banner {index + 1}</h2>
              <span className="product-status-badge rounded-full px-2.5 py-1 text-xs font-medium" data-status={banner.is_active ? "active" : "inactive"}>
                {banner.is_active ? "Active" : "Inactive"}
              </span>
            </div>

            <div className="grid grid-cols-[minmax(0,1fr)_5rem] gap-3">
              <figure className="image-drop overflow-hidden rounded-xl">
                {/* eslint-disable-next-line @next/next/no-img-element -- backend media, no optimizer (as ProductImage) */}
                <img src={banner.desktop_image} alt={banner.alt_text || `Banner ${index + 1} (desktop)`} className="block h-auto w-full" />
                <figcaption className="sr-only">Desktop image</figcaption>
              </figure>
              <figure className="flex flex-col gap-1">
                {banner.mobile_image ? (
                  <div className="image-drop overflow-hidden rounded-xl">
                    {/* eslint-disable-next-line @next/next/no-img-element -- backend media, no optimizer */}
                    <img src={banner.mobile_image} alt="" className="block h-auto w-full" />
                  </div>
                ) : (
                  <div className="image-drop flex aspect-[4/5] items-center justify-center rounded-xl p-1.5 text-center text-[11px] leading-tight showcase-muted">
                    Same as desktop
                  </div>
                )}
                <figcaption className="showcase-muted text-xs">Mobile</figcaption>
              </figure>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
              <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    type="checkbox"
                    role="switch"
                    checked={banner.is_active}
                    disabled={busyId === banner.id}
                    onChange={() => toggleActive(banner)}
                    className="form-check h-4 w-4"
                  />
                  Active: {banner.is_active ? "ON" : "OFF"}
                </label>
                <span className="flex items-center gap-1.5">
                  Order: <span className="font-semibold">{index + 1}</span>
                  <button
                    type="button"
                    onClick={() => move(index, -1)}
                    disabled={index === 0 || busyId !== null}
                    aria-label={`Move banner ${index + 1} up`}
                    className="auth-btn auth-btn--outline flex h-7 w-7 items-center justify-center rounded-full"
                  >
                    <FiArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => move(index, 1)}
                    disabled={index === banners.length - 1 || busyId !== null}
                    aria-label={`Move banner ${index + 1} down`}
                    className="auth-btn auth-btn--outline flex h-7 w-7 items-center justify-center rounded-full"
                  >
                    <FiArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </span>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setEditing(banner)}
                  className="auth-btn auth-btn--outline inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium"
                >
                  <FiEdit2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => setPendingDelete(banner)}
                  className="auth-btn auth-btn--outline auth-error inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium"
                >
                  <FiTrash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Delete
                </button>
              </div>
            </div>
          </li>
        ))}
        {Array.from({ length: MAX_BANNERS - banners.length }, (_, i) => banners.length + i).map((slot) => (
          <li key={`empty-${slot}`} className="dashboard-card flex min-w-0 flex-1 flex-col gap-4 rounded-2xl p-5">
            <h2 className="custom-font text-lg font-bold">Banner {slot + 1}</h2>
            <ImageDropzone
              label={`Banner ${slot + 1}`}
              onFile={uploadNew}
              busy={uploading && slot === banners.length}
              disabled={uploading}
            />
          </li>
        ))}
      </ul>

      {editing && (
        <BannerForm
          banner={editing === "new" ? null : editing}
          nextOrder={banners.length ? Math.max(...banners.map((b) => b.sort_order)) + 1 : 0}
          onClose={() => setEditing(null)}
          onSaved={(banner) => {
            saved(banner);
            setEditing(null);
          }}
        />
      )}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete Banner?"
        description="Are you sure you want to delete this banner? Its images will be removed and it will disappear from the homepage."
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}

// Add / Edit one banner: replace images, alt text, active. Editing never creates a second record.
function BannerForm({ banner, nextOrder, onClose, onSaved }) {
  const isEdit = Boolean(banner);
  const [desktop, setDesktop] = useState({ url: banner?.desktop_image ?? null, file: null, removed: false });
  const [mobile, setMobile] = useState({ url: banner?.mobile_image ?? null, file: null, removed: false });
  const [altText, setAltText] = useState(banner?.alt_text ?? "");
  const [isActive, setIsActive] = useState(banner?.is_active ?? true);
  const [saving, setSaving] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!desktop.file && !desktop.url) return notify.error("A desktop banner image is required.");
    const fd = new FormData();
    const alt = altText.trim();
    fd.append("alt_text", alt);
    fd.append("title", (alt || banner?.title || "Hero banner").slice(0, 120)); // internal label only
    fd.append("is_active", String(isActive));
    if (!isEdit) fd.append("sort_order", String(nextOrder));
    if (desktop.file) fd.append("desktop_image", desktop.file);
    if (mobile.file) fd.append("mobile_image", mobile.file);

    setSaving(true);
    let res = await bannerRequest(isEdit ? `/${banner.id}` : "", { method: isEdit ? "PATCH" : "POST", body: fd });
    if (res.ok && res.data?.id && mobile.removed && !mobile.file && res.data.mobile_image) {
      // multipart can't send "no file": clear the mobile image with a small JSON update
      res = await bannerRequest(`/${res.data.id}`, { method: "PATCH", body: { mobile_image: null } });
    }
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, isEdit ? "Unable to update the banner." : "Unable to add the banner."));
    notify.success(isEdit ? "Banner updated successfully." : "Banner added successfully.");
    onSaved(res.data);
  }

  return (
    <Modal open title={isEdit ? "Edit Banner" : "Add Banner"} onClose={() => !saving && onClose()} wide>
      <form onSubmit={submit} noValidate className="flex flex-col gap-5">
        <SingleImageInput id="banner-desktop" label="Desktop image" required contain value={desktop} onChange={setDesktop} />
        <SingleImageInput id="banner-mobile" label="Mobile image (optional)" clearable contain value={mobile} onChange={setMobile} />
        <p className="showcase-muted -mt-2 text-xs">
          JPG, PNG or WEBP, up to 5 MB. The banner fills the screen height, so keep text and faces near the centre; a
          landscape desktop image and a portrait mobile image fit best. Without a mobile image, phones show the desktop one.
        </p>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="banner-alt" className="text-sm font-medium">Alt text</label>
          <input
            id="banner-alt"
            type="text"
            maxLength={150}
            value={altText}
            onChange={(e) => setAltText(e.target.value)}
            placeholder="Describe the banner for screen readers"
            className="checkout-input w-full rounded-lg px-3 py-2.5 text-sm"
          />
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="form-check h-4 w-4" />
          Active (show on the homepage)
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={saving} className="auth-btn auth-btn--outline rounded-full px-5 py-2 text-sm font-medium">
            Cancel
          </button>
          <button type="submit" disabled={saving} className="auth-btn auth-btn--primary rounded-full px-5 py-2 text-sm font-medium">
            {saving ? "Saving…" : isEdit ? "Save Changes" : "Add Banner"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
