"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { notify } from "@/lib/notify";
import { catalogFetch, errorText } from "@/lib/productAdmin";
import { parentOptions } from "@/lib/categoryAdmin";
import { SingleImageInput } from "../products/ImageInputs";

const INPUT = "checkout-input rounded-lg px-3 py-2.5 text-sm";

// Add / Edit Category over the EXISTING /admin/categories/ API (AdminCategorySerializer), sent as multipart so the
// image travels with the rest; the backend removes a replaced/cleared image file itself (ReplacedFilesMixin).
// Fields are the serializer's own: slug, name, image, parent (an id, or null for a top-level category),
// description, is_active. sort_order and the SEO fields aren't on this form and are left as they are.
export default function CategoryForm({ category = null }) {
  const router = useRouter();
  const isEdit = Boolean(category);

  const [name, setName] = useState(category?.name ?? "");
  const [slug, setSlug] = useState(category?.slug ?? "");
  const [parent, setParent] = useState(category?.parent ? String(category.parent) : "");
  const [description, setDescription] = useState(category?.description ?? "");
  const [isActive, setIsActive] = useState(category?.is_active ?? true); // the model's default is active
  const [image, setImage] = useState({ url: category?.image ?? null, file: null, removed: false });
  const [tree, setTree] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    catalogFetch("categories/tree").then((res) => {
      if (cancelled) return;
      if (!res.ok) notify.error("Parent categories couldn't be loaded. Please refresh.");
      setTree(res.ok ? res.data : []);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const options = parentOptions(tree ?? [], category?.id ?? null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    if (!name.trim()) return notify.error("Name is required.");

    const fd = new FormData();
    fd.append("name", name.trim());
    // Blank slug -> generated from the name; an unchanged one isn't re-sent so it doesn't count as hand-set.
    const trimmedSlug = slug.trim();
    if (isEdit ? trimmedSlug !== category.slug : trimmedSlug) fd.append("slug", trimmedSlug);
    fd.append("parent", parent); // "" -> null (top level)
    fd.append("description", description);
    fd.append("is_active", String(isActive));
    if (image.file) fd.append("image", image.file);
    else if (image.removed) fd.append("image", "");

    setSubmitting(true);
    const res = await catalogFetch(isEdit ? `categories/${category.id}` : "categories", { method: isEdit ? "PATCH" : "POST", body: fd });
    if (!res.ok) {
      setSubmitting(false);
      return notify.error(errorText(res, isEdit ? "Unable to update the category. Please try again." : "Unable to create the category. Please try again."));
    }
    notify.success(isEdit ? "Category updated successfully." : "Category created successfully.");
    router.push("/dashboard/CCE/categories");
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      <section className="dashboard-card rounded-2xl p-5 sm:p-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="cf-name" className="text-sm font-medium">
              Name <span aria-hidden="true">*</span>
            </label>
            <input id="cf-name" type="text" maxLength={120} value={name} onChange={(e) => setName(e.target.value)} className={INPUT} />
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="cf-slug" className="text-sm font-medium">
              Slug <span className="showcase-muted font-normal">(Optional)</span>
            </label>
            <input id="cf-slug" type="text" maxLength={255} value={slug} onChange={(e) => setSlug(e.target.value)} className={INPUT} />
            <p className="showcase-muted text-xs">Leave blank to generate it from the name.</p>
          </div>

          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="cf-parent" className="text-sm font-medium">
              Parent
            </label>
            <select id="cf-parent" value={parent} onChange={(e) => setParent(e.target.value)} disabled={tree === null} className={INPUT}>
              <option value="">{tree === null ? "Loading categories..." : "No Parent"}</option>
              {options.map((o) => (
                <option key={o.id} value={o.id}>
                  {`${"  ".repeat(o.depth)}${o.depth ? "↳ " : ""}${o.name}${o.is_active ? "" : " (inactive)"}`}
                </option>
              ))}
            </select>
            <p className="showcase-muted text-xs">
              {isEdit ? "A category can't be moved under itself or one of its sub-categories." : "Choose No Parent for a top-level category."}
            </p>
          </div>

          <div className="flex flex-col justify-center gap-1.5">
            <span className="text-sm font-medium">Is Active</span>
            <label htmlFor="cf-active" className="flex cursor-pointer items-start gap-2.5 text-sm">
              <input id="cf-active" type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="form-check mt-0.5 h-4 w-4 shrink-0" />
              <span>
                {isActive ? "Active" : "Inactive"}
                <span className="showcase-muted block text-xs">An inactive category (and everything under it) is hidden from the shop.</span>
              </span>
            </label>
          </div>

          <div className="flex min-w-0 flex-col gap-1.5 sm:col-span-2">
            <label htmlFor="cf-description" className="text-sm font-medium">
              Description <span className="showcase-muted font-normal">(Optional)</span>
            </label>
            <textarea id="cf-description" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} className={INPUT} />
          </div>

          <div className="sm:col-span-2">
            <SingleImageInput id="cf-image" label="Image" clearable value={image} onChange={setImage} />
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Link href="/dashboard/CCE/categories" className="auth-btn auth-btn--outline rounded-full px-6 py-2.5 text-sm font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={submitting} aria-busy={submitting} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {submitting ? (isEdit ? "Saving Category..." : "Creating Category...") : isEdit ? "Save Changes" : "Create Category"}
        </button>
      </div>
    </form>
  );
}
