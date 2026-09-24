"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { notify } from "@/lib/notify";
import { catalogFetch, errorText } from "@/lib/productAdmin";
import { SingleImageInput } from "../products/ImageInputs";

const INPUT = "checkout-input rounded-lg px-3 py-2.5 text-sm";

// Add / Edit Brand over the EXISTING /admin/brands/ API (AdminBrandSerializer: name, slug, logo, description,
// is_active), sent as multipart so the logo travels with the rest; the backend removes a replaced/cleared logo
// file itself (ReplacedFilesMixin) and rejects a duplicate name (case-insensitive).
export default function BrandForm({ brand = null }) {
  const router = useRouter();
  const isEdit = Boolean(brand);

  const [name, setName] = useState(brand?.name ?? "");
  const [slug, setSlug] = useState(brand?.slug ?? "");
  const [description, setDescription] = useState(brand?.description ?? "");
  const [isActive, setIsActive] = useState(brand?.is_active ?? true); // the model's default is active
  const [logo, setLogo] = useState({ url: brand?.logo ?? null, file: null, removed: false });
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    if (!name.trim()) return notify.error("Name is required.");

    const fd = new FormData();
    fd.append("name", name.trim());
    // Blank slug -> generated from the name; an unchanged one isn't re-sent so it doesn't count as hand-set.
    const trimmedSlug = slug.trim();
    if (isEdit ? trimmedSlug !== brand.slug : trimmedSlug) fd.append("slug", trimmedSlug);
    fd.append("description", description);
    fd.append("is_active", String(isActive));
    if (logo.file) fd.append("logo", logo.file);
    else if (logo.removed) fd.append("logo", "");

    setSubmitting(true);
    const res = await catalogFetch(isEdit ? `brands/${brand.id}` : "brands", { method: isEdit ? "PATCH" : "POST", body: fd });
    if (!res.ok) {
      setSubmitting(false);
      return notify.error(errorText(res, isEdit ? "Unable to update the brand. Please try again." : "Unable to create the brand. Please try again."));
    }
    notify.success(isEdit ? "Brand updated successfully." : "Brand created successfully.");
    router.push("/dashboard/CCE/brands");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <section className="dashboard-card rounded-2xl p-5 sm:p-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="bf-name" className="text-sm font-medium">
              Name <span aria-hidden="true">*</span>
            </label>
            <input id="bf-name" type="text" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} className={INPUT} />
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="bf-slug" className="text-sm font-medium">
              Slug <span className="showcase-muted font-normal">(Optional)</span>
            </label>
            <input id="bf-slug" type="text" maxLength={255} value={slug} onChange={(e) => setSlug(e.target.value)} className={INPUT} />
            <p className="showcase-muted text-xs">Leave blank to generate it from the name.</p>
          </div>

          <div className="sm:col-span-2">
            <SingleImageInput id="bf-logo" label="Logo" clearable contain value={logo} onChange={setLogo} />
          </div>

          <div className="flex min-w-0 flex-col gap-1.5 sm:col-span-2">
            <label htmlFor="bf-description" className="text-sm font-medium">
              Description <span className="showcase-muted font-normal">(Optional)</span>
            </label>
            <textarea id="bf-description" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} className={INPUT} />
          </div>

          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-sm font-medium">Is Active</span>
            <label htmlFor="bf-active" className="flex cursor-pointer items-start gap-2.5 text-sm">
              <input id="bf-active" type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="form-check mt-0.5 h-4 w-4 shrink-0" />
              <span>
                {isActive ? "Active" : "Inactive"}
                <span className="showcase-muted block text-xs">An inactive brand is hidden from the shop&apos;s brand list; products keep it.</span>
              </span>
            </label>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Link href="/dashboard/CCE/brands" className="auth-btn auth-btn--outline rounded-full px-6 py-2.5 text-sm font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={submitting} aria-busy={submitting} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {submitting ? (isEdit ? "Saving Brand..." : "Creating Brand...") : isEdit ? "Save Changes" : "Create Brand"}
        </button>
      </div>
    </form>
  );
}
