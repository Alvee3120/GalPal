const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";
const REVALIDATE_SECONDS = 60;
export const DEFAULT_CURRENCY_SYMBOL = "৳";
// Cache tag for the public site settings; the admin Site Settings save revalidates it (app/api/admin/site-settings).
export const SITE_SETTINGS_TAG = "site-settings";

// The PUBLIC site settings (GET /site-settings/ — the backend's allow-listed public fields only), cached and shared by
// every server component that needs them. null if the backend can't be reached.
export async function getSiteSettings() {
  try {
    const res = await fetch(`${API_BASE_URL}/site-settings/`, {
      next: { revalidate: REVALIDATE_SECONDS, tags: [SITE_SETTINGS_TAG] },
    });
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// Currency comes from the site settings so it is never hardcoded; falls back to the default symbol.
export async function getCurrencySymbol() {
  const settings = await getSiteSettings();
  return settings?.currency_symbol || DEFAULT_CURRENCY_SYMBOL;
}

// The store's contact details and social links for the footer (Admin → Site Settings). Only what's filled in.
const SOCIAL_KEYS = ["facebook_url", "instagram_url", "youtube_url", "tiktok_url", "x_url", "linkedin_url"];

export async function getContactDetails() {
  const settings = await getSiteSettings();
  const text = (key) => (typeof settings?.[key] === "string" ? settings[key].trim() : "");
  return {
    phone: text("phone"),
    email: text("email"),
    address: text("address"),
    supportHours: text("support_hours"),
    // Stored as digits with country code (e.g. 8801712345678) by the backend; used for a wa.me chat link.
    whatsapp: text("whatsapp_number").replace(/\D/g, ""),
    // Only http(s) links (the backend enforces this too), keyed by field name, e.g. { facebook_url: "https://…" }.
    socials: Object.fromEntries(SOCIAL_KEYS.map((key) => [key, text(key)]).filter(([, url]) => /^https?:\/\//i.test(url))),
  };
}
