// User-facing text for a failed API call: the backend's own validation message when it sent one
// for a 4xx (e.g. "Product not found."), otherwise the caller's friendly fallback. Never raw errors.
export function messageFor(err, fallback) {
  const detail = err.details && Object.values(err.details).flat().find((m) => typeof m === "string" && m.length <= 160);
  return err.status >= 400 && err.status < 500 && detail ? detail : fallback;
}
