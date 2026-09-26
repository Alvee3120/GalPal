// Video Card Management helpers (app/api/admin/videos). Upload rules mirror the backend's validators
// (apps.core.validators.validate_video_file: MP4/WEBM, VIDEO_MAX_UPLOAD_SIZE = 50 MB by default) — checked here only to
// fail fast; the backend checks every file (including its real format, not just the extension).
export const VIDEO_ACCEPT = "video/mp4,video/webm";
export const VIDEO_MAX_BYTES = 50 * 1024 * 1024;

export function checkVideo(file) {
  const ext = file.name.split(".").pop()?.toLowerCase();
  if (!["mp4", "webm"].includes(ext)) return "Unsupported video format. Allowed: MP4, WEBM.";
  if (file.size > VIDEO_MAX_BYTES) return "Video is too large. Maximum allowed size is 50 MB.";
  return null;
}

export async function videoFetch(path = "", { method = "GET" } = {}) {
  try {
    const res = await fetch(`/api/admin/videos${path}`, { method, cache: "no-store" });
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, data };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

// Sends a FormData with upload progress (fetch can't report it): onProgress(0..100). Resolves { ok, status, data }.
export function videoUpload(path, method, formData, onProgress) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, `/api/admin/videos${path}`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let data = null;
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        data = null;
      }
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, data });
    };
    xhr.onerror = () => resolve({ ok: false, status: 0, data: null });
    xhr.send(formData);
  });
}
