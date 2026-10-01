// Client helper for the Customer Care admin API (Module 14) via the /api/admin/care proxy. Resolves to
// { ok, status, data } and never throws, like the other dashboard fetch helpers.
export async function careFetch(path, { method = "GET", body } = {}) {
  try {
    const res = await fetch(`/api/admin/care/${path}`, {
      method,
      cache: "no-store",
      body: body === undefined ? undefined : JSON.stringify(body),
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    });
    return { ok: res.ok, status: res.status, data: res.status === 204 ? null : await res.json().catch(() => null) };
  } catch {
    return { ok: false, status: 0, data: null };
  }
}

export const MESSAGE_STATUS = [
  { value: "new", label: "New" },
  { value: "in_progress", label: "In progress" },
  { value: "resolved", label: "Resolved" },
];
export const MESSAGE_STATUS_LABEL = Object.fromEntries(MESSAGE_STATUS.map((s) => [s.value, s.label]));
