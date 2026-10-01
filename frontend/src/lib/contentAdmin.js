// Client helper for the Content admin API (Module 15) via the /api/admin/content proxy. Resolves to
// { ok, status, data } and never throws, like the other dashboard fetch helpers.
export async function contentFetch(path, { method = "GET", body } = {}) {
  try {
    const res = await fetch(`/api/admin/content/${path}`, {
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

// Mirrors apps.content.services.STANDARD_PAGES: the storefront route each standard page replaces.
export const STANDARD_PAGE_PATH = {
  about: "/about",
  "privacy-policy": "/privacy-policy",
  terms: "/terms",
  "return-and-cancellation-policy": "/return-and-cancellation-policy",
  "shipping-policy": "/shipping-policy",
};

export const pagePath = (slug) => STANDARD_PAGE_PATH[slug] ?? `/pages/${slug}`;

export function slugify(text) {
  return text
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}
