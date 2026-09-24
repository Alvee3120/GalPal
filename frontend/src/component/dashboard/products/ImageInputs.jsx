"use client";

import { useEffect, useId, useMemo, useRef } from "react";
import { FiArrowDown, FiArrowUp, FiImage, FiUpload, FiX } from "react-icons/fi";
import { notify } from "@/lib/notify";

// Same rule as the backend's apps.core.validators.validate_image_file (JPG/PNG/WEBP, IMAGE_MAX_UPLOAD_SIZE = 5 MB
// by default). Checked here only to fail fast; the backend still validates every upload.
const ACCEPT = "image/jpeg,image/png,image/webp";
const MAX_BYTES = 5 * 1024 * 1024;

export function checkImage(file) {
  if (!ACCEPT.split(",").includes(file.type)) return "Unsupported image format. Allowed: JPG, PNG, WEBP.";
  if (file.size > MAX_BYTES) return "Image is too large. Maximum allowed size is 5 MB.";
  return null;
}

// An object URL for a freshly picked File (revoked when it changes), or the saved image's own URL.
function usePreview(file, url) {
  const objectUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => objectUrl && URL.revokeObjectURL(objectUrl), [objectUrl]);
  return objectUrl ?? url ?? null;
}

// One image field (feature image, OG image, a variant's image). `value` is { url, file, removed }: `url` is what the
// backend already has, `file` a newly picked replacement, `removed` asks to clear it (only offered when `clearable`,
// i.e. the backend field is nullable — the feature image is required, so it can be replaced but not removed).
// `contain` shows the whole image uncropped (logos).
export function SingleImageInput({ id, label, value, onChange, clearable = false, required = false, compact = false, contain = false }) {
  const inputRef = useRef(null);
  const fallbackId = useId();
  const inputId = id ?? fallbackId;
  const preview = usePreview(value.file, value.removed ? null : value.url);

  function pick(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const problem = checkImage(file);
    if (problem) return notify.error(problem);
    onChange({ ...value, file, removed: false });
  }

  function clear() {
    onChange(value.file ? { ...value, file: null } : { ...value, removed: true });
  }

  const size = compact ? "h-20 w-20" : "h-32 w-32";
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium">
        {label} {required && <span aria-hidden="true">*</span>}
      </span>
      <div className="flex items-center gap-3">
        <div className={`image-drop relative flex ${size} shrink-0 items-center justify-center overflow-hidden rounded-xl`}>
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element -- local object URLs / remote media, no optimizer
            <img src={preview} alt="" className={`h-full w-full ${contain ? "object-contain p-2" : "object-cover"}`} />
          ) : (
            <FiImage className="showcase-muted h-6 w-6" aria-hidden="true" />
          )}
        </div>
        <div className="flex flex-col items-start gap-2">
          <input ref={inputRef} id={inputId} type="file" accept={ACCEPT} onChange={pick} className="sr-only" />
          <button type="button" onClick={() => inputRef.current?.click()} className="auth-btn auth-btn--outline inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium">
            <FiUpload className="h-3.5 w-3.5" aria-hidden="true" />
            {preview ? "Replace" : "Upload"}
          </button>
          {preview && (value.file || clearable) && (
            <button type="button" onClick={clear} className="auth-error inline-flex items-center gap-1 text-xs font-medium">
              <FiX className="h-3.5 w-3.5" aria-hidden="true" />
              {value.file && value.url && !value.removed ? "Undo replace" : "Remove"}
            </button>
          )}
          {!compact && <span className="showcase-muted text-xs">JPG, PNG or WEBP, up to 5 MB.</span>}
        </div>
      </div>
    </div>
  );
}

function GalleryThumb({ item }) {
  const preview = usePreview(item.file, item.url);
  // eslint-disable-next-line @next/next/no-img-element -- local object URLs / remote media, no optimizer
  return <img src={preview} alt="" className="h-full w-full object-cover" />;
}

// Product gallery (apps.catalog.models.ProductImage, ordered by sort_order). `items` are { key, id?, url?, file? }:
// saved images carry their backend `id`, new ones a `file`. Reordering here is saved with the existing
// images/reorder/ endpoint; the feature image is a separate field (Product.feature_image), not one of these.
export function GalleryInput({ items, onChange }) {
  const inputRef = useRef(null);

  function add(e) {
    const files = [...(e.target.files ?? [])];
    e.target.value = "";
    const good = [];
    for (const file of files) {
      const problem = checkImage(file);
      if (problem) notify.error(`${file.name}: ${problem}`);
      else good.push({ key: `new-${crypto.randomUUID()}`, file });
    }
    if (good.length) onChange([...items, ...good]);
  }

  function move(index, delta) {
    const next = [...items];
    const [item] = next.splice(index, 1);
    next.splice(index + delta, 0, item);
    onChange(next);
  }

  return (
    <div className="flex flex-col gap-3">
      {items.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {items.map((item, index) => (
            <li key={item.key} className="image-drop relative aspect-square overflow-hidden rounded-xl">
              <GalleryThumb item={item} />
              <div className="absolute inset-x-1.5 bottom-1.5 flex items-center justify-between gap-1">
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => move(index, -1)}
                    disabled={index === 0}
                    title="Move earlier"
                    aria-label={`Move image ${index + 1} earlier`}
                    className="icon-action icon-action--overlay flex h-7 w-7 items-center justify-center rounded-full disabled:opacity-40"
                  >
                    <FiArrowUp className="h-3.5 w-3.5 -rotate-90" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => move(index, 1)}
                    disabled={index === items.length - 1}
                    title="Move later"
                    aria-label={`Move image ${index + 1} later`}
                    className="icon-action icon-action--overlay flex h-7 w-7 items-center justify-center rounded-full disabled:opacity-40"
                  >
                    <FiArrowDown className="h-3.5 w-3.5 -rotate-90" aria-hidden="true" />
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => onChange(items.filter((i) => i.key !== item.key))}
                  title="Remove image"
                  aria-label={`Remove image ${index + 1}`}
                  className="icon-action icon-action--overlay icon-action--danger flex h-7 w-7 items-center justify-center rounded-full"
                >
                  <FiX className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              </div>
              {!item.id && <span className="product-status-badge absolute left-1.5 top-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium" data-status="draft">New</span>}
            </li>
          ))}
        </ul>
      )}
      <div>
        <input ref={inputRef} type="file" accept={ACCEPT} multiple onChange={add} className="sr-only" aria-label="Add product images" />
        <button type="button" onClick={() => inputRef.current?.click()} className="auth-btn auth-btn--outline inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium">
          <FiUpload className="h-3.5 w-3.5" aria-hidden="true" />
          Add Images
        </button>
        <span className="showcase-muted ml-3 text-xs">JPG, PNG or WEBP, up to 5 MB each.</span>
      </div>
    </div>
  );
}
