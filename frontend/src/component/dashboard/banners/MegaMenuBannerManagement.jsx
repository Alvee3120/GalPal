"use client";

import { useState } from "react";
import { FiAlertCircle, FiEdit2, FiTrash2 } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import Modal from "@/component/shared/Modal";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import { SingleImageInput } from "@/component/dashboard/products/ImageInputs";
import ImageDropzone from "./ImageDropzone";

// The three fixed slots, in display order. The backend allows one banner per slot (apps.banners.models.MegaMenuBanner).
const SLOTS = [
  { value: "square_1", label: "Square banner 1", hint: "Left square (3rd column)" },
  { value: "square_2", label: "Square banner 2", hint: "Right square (4th column)" },
  { value: "wide", label: "Wide banner", hint: "Wide banner (5th–6th columns)" },
];

async function bannerRequest(path, { method = "GET", body } = {}) {
  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  try {
    const r = await fetch(`/api/admin/mega-menu-banners${path}`, {
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

// Admin → Mega Menu: the three images in the Shop mega menu — two square banners (columns 3 and 4) and one wide banner
// (columns 5–6). One banner per slot over the apps.banners admin API; changes revalidate the storefront menu.
export default function MegaMenuBannerManagement({ initialBanners }) {
  const [banners, setBanners] = useState(initialBanners ?? []);
  const [editing, setEditing] = useState(null); // a slot value, or null
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [uploadingSlot, setUploadingSlot] = useState(null);

  if (!initialBanners) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="custom-font text-2xl sm:text-3xl">Mega Menu Banners</h1>
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <FiAlertCircle className="h-8 w-8" aria-hidden="true" />
          <p className="text-sm">Unable to load the mega menu banners. Please refresh the page.</p>
        </div>
      </div>
    );
  }

  const bySlot = Object.fromEntries((banners ?? []).map((b) => [b.slot, b]));

  function saved(banner) {
    if (!banner?.id) return;
    setBanners((list) => [...list.filter((b) => b.slot !== banner.slot), banner]);
  }

  // An empty slot's drop zone: the image becomes a new, active banner for that slot.
  async function uploadNew(slot, file) {
    const fd = new FormData();
    fd.append("slot", slot.value);
    fd.append("title", slot.label); // internal label only
    fd.append("is_active", "true");
    fd.append("image", file);
    setUploadingSlot(slot.value);
    const res = await bannerRequest("", { method: "POST", body: fd });
    setUploadingSlot(null);
    if (!res.ok) return notify.error(errorText(res, "Unable to upload the banner."));
    saved(res.data);
    notify.success("Banner uploaded. Use Edit to set its link or alt text.");
  }

  async function confirmDelete() {
    const target = pendingDelete; // captured now: the state is cleared below, before React applies the list update
    if (!target || deleting) return;
    setDeleting(true);
    const res = await bannerRequest(`/${target.id}`, { method: "DELETE" });
    setDeleting(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to delete the banner."));
    setBanners((list) => list.filter((b) => b.slot !== target.slot));
    setPendingDelete(null);
    notify.success("Banner deleted.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Mega Menu Banners</h1>
        <p className="showcase-muted text-sm">
          The three images in the Shop mega menu: two square banners and one wide banner. Hidden slots simply don&apos;t show.
        </p>
      </div>

      <ul className="flex flex-col gap-4 lg:flex-row lg:items-stretch">
        {SLOTS.map((slot) => {
          const banner = bySlot[slot.value];
          const status = !banner ? "draft" : banner.is_active ? "active" : "inactive";
          return (
            <li key={slot.value} className="dashboard-card flex min-w-0 flex-1 flex-col gap-4 rounded-2xl p-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h2 className="custom-font text-lg font-bold">{slot.label}</h2>
                  <p className="showcase-muted text-xs">{slot.hint}</p>
                </div>
                <span className="product-status-badge rounded-full px-2.5 py-1 text-xs font-medium" data-status={status}>
                  {!banner ? "Empty" : banner.is_active ? "Active" : "Inactive"}
                </span>
              </div>

              {banner ? (
                <>
                  <figure className={`image-drop overflow-hidden rounded-xl ${slot.value === "wide" ? "aspect-[16/7]" : "aspect-[4/5]"}`}>
                    {/* eslint-disable-next-line @next/next/no-img-element -- backend media, no optimizer (as ProductImage) */}
                    <img src={banner.image} alt={banner.alt_text || slot.label} className="block h-full w-full object-cover" />
                  </figure>
                  <div className="mt-auto flex flex-wrap justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setEditing(slot.value)}
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
                </>
              ) : (
                <ImageDropzone
                  label={slot.label}
                  onFile={(file) => uploadNew(slot, file)}
                  busy={uploadingSlot === slot.value}
                  disabled={uploadingSlot !== null}
                />
              )}
            </li>
          );
        })}
      </ul>

      {editing && (
        <BannerForm
          slot={SLOTS.find((s) => s.value === editing)}
          banner={bySlot[editing] ?? null}
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
        description="Are you sure you want to delete this mega menu banner? Its image will be removed and the slot will be empty."
        confirmLabel="Delete"
        busyLabel="Deleting..."
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => !deleting && setPendingDelete(null)}
      />
    </div>
  );
}

// Add / Edit one slot's banner: image, alt text, link and active. One banner per slot.
function BannerForm({ slot, banner, onClose, onSaved }) {
  const isEdit = Boolean(banner);
  const [image, setImage] = useState({ url: banner?.image ?? null, file: null, removed: false });
  const [altText, setAltText] = useState(banner?.alt_text ?? "");
  const [linkUrl, setLinkUrl] = useState(banner?.link_url ?? "");
  const [isActive, setIsActive] = useState(banner?.is_active ?? true);
  const [saving, setSaving] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!image.file && !image.url) return notify.error("A banner image is required.");
    const fd = new FormData();
    fd.append("alt_text", altText.trim());
    fd.append("link_url", linkUrl.trim());
    fd.append("title", slot.label); // internal label only
    fd.append("is_active", String(isActive));
    if (!isEdit) fd.append("slot", slot.value);
    if (image.file) fd.append("image", image.file);

    setSaving(true);
    const res = await bannerRequest(isEdit ? `/${banner.id}` : "", { method: isEdit ? "PATCH" : "POST", body: fd });
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, isEdit ? "Unable to update the banner." : "Unable to add the banner."));
    notify.success(isEdit ? "Banner updated successfully." : "Banner added successfully.");
    onSaved(res.data);
  }

  return (
    <Modal open title={`${isEdit ? "Edit" : "Add"} ${slot.label}`} onClose={() => !saving && onClose()} wide>
      <form onSubmit={submit} noValidate className="flex flex-col gap-5">
        <SingleImageInput id="mega-menu-image" label="Image" required value={image} onChange={setImage} />
        <p className="showcase-muted -mt-2 text-xs">
          JPG, PNG or WEBP, up to 5 MB.{" "}
          {slot.value === "wide" ? "A wide, landscape image fits best." : "A square or portrait image fits best."}
        </p>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="mega-menu-link" className="text-sm font-medium">Link (optional)</label>
          <input
            id="mega-menu-link"
            type="text"
            maxLength={500}
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="/shop?category=skincare or https://…"
            className="checkout-input w-full rounded-lg px-3 py-2.5 text-sm"
          />
          <span className="showcase-muted text-xs">A site path (opens in this shop) or a full http(s) URL (opens in a new tab).</span>
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="mega-menu-alt" className="text-sm font-medium">Alt text</label>
          <input
            id="mega-menu-alt"
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
          Active (show in the Shop menu)
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
