// Server-side readers for the public content endpoints (Module 15 — apps.content). Cached and tagged so an Admin save
// in the dashboard (app/api/admin/content) shows up on the storefront right away. All return null / [] on failure so a
// page always has its built-in fallback.
const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 300;
export const CONTENT_TAG = "content";

async function getJson(path) {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { next: { revalidate: REVALIDATE_SECONDS, tags: [CONTENT_TAG] } });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// An active CMS page (title, content, meta_title, meta_description, updated_at), or null.
export function getContentPage(slug) {
  return getJson(`/pages/${encodeURIComponent(slug)}/`);
}

export async function getFaqs() {
  const data = await getJson("/faqs/");
  return Array.isArray(data) ? data : [];
}

export async function getAnnouncements() {
  const data = await getJson("/announcements/");
  return Array.isArray(data) ? data : [];
}

// "1 October 2026" from an ISO timestamp — the "Last updated" line on CMS-backed pages.
export function formatUpdated(iso) {
  const d = iso ? new Date(iso) : null;
  return d && !Number.isNaN(d.getTime()) ? d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Dhaka" }) : "";
}

// The Admin's homepage category sections (Admin → Homepage Sections): active ones whose category is visible, already in
// display order (before the video, then after; sort order within each). [] if the backend can't be reached.
export async function getHomepageCategorySections() {
  const data = await getJson("/homepage/category-sections/");
  return Array.isArray(data) ? data : [];
}
