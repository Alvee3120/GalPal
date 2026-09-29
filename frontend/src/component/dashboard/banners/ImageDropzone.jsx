"use client";

import { useId, useRef, useState } from "react";
import { FiUploadCloud } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { checkImage } from "@/component/dashboard/products/ImageInputs";

const ACCEPT = "image/jpeg,image/png,image/webp";

// A dashed "Choose a file or drag & drop it here" box for one image. Validated with the same rule as every other
// dashboard image (checkImage: JPG/PNG/WEBP up to 5 MB — the backend's validate_image_file checks again). Keyboard
// users use the Browse File button; the whole box also accepts a dropped file.
export default function ImageDropzone({ onFile, busy = false, disabled = false, label = "Banner image" }) {
  const inputRef = useRef(null);
  const hintId = useId();
  const [dragging, setDragging] = useState(false);
  const inactive = busy || disabled;

  function take(file) {
    if (!file || inactive) return;
    const problem = checkImage(file);
    if (problem) return notify.error(problem);
    onFile(file);
  }

  return (
    <div
      className="image-dropzone flex flex-1 flex-col items-center justify-center gap-2 rounded-2xl px-6 py-10 text-center"
      data-dragging={dragging || undefined}
      data-busy={busy || undefined}
      onDragOver={(e) => {
        e.preventDefault();
        if (!inactive) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        take(e.dataTransfer.files?.[0]);
      }}
    >
      <FiUploadCloud className="image-dropzone__icon h-7 w-7" aria-hidden="true" />
      <p className="mt-1 text-base font-medium">{busy ? "Uploading…" : "Choose a file or drag & drop it here"}</p>
      <p id={hintId} className="showcase-muted text-sm">
        JPEG, PNG and WEBP formats, up to 5MB
      </p>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          take(file);
        }}
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={inactive}
        aria-label={`Browse file: ${label}`}
        aria-describedby={hintId}
        className="auth-btn auth-btn--outline mt-2 rounded-lg px-5 py-2 text-sm font-medium"
      >
        Browse File
      </button>
    </div>
  );
}
