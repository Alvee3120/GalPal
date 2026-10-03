// The Site Settings fields the admin dashboard edits (Admin → Site Settings), mirroring the backend's SiteSettings
// model limits (apps.site_settings.models). The backend validates them too (a real email address; social links must
// be http(s) URLs).
export const SITE_SETTINGS_GROUPS = [
  {
    title: "Store & Contact",
    fields: [
      { key: "site_name", label: "Store Name", type: "text", maxLength: 100, required: true, hint: "Shown on invoices." },
      { key: "phone", label: "Phone Number", type: "tel", maxLength: 30, hint: "Footer and invoices." },
      { key: "email", label: "Email", type: "email", maxLength: 254, hint: "Footer and invoices." },
      { key: "whatsapp_number", label: "WhatsApp Number", type: "tel", maxLength: 20, hint: "Contact page chat button. e.g. 01712345678" },
      { key: "support_hours", label: "Support Hours", type: "text", maxLength: 200, hint: "Footer and contact page. e.g. Sat–Thu, 10am–8pm", wide: true },
      { key: "address", label: "Address", type: "textarea", maxLength: 500, hint: "Footer and invoices." },
    ],
  },
  {
    title: "Social Links",
    note: "Each link you add shows as an icon in the footer; leave a field empty to hide that icon.",
    fields: [
      { key: "facebook_url", label: "Facebook URL", type: "url", maxLength: 300 },
      { key: "instagram_url", label: "Instagram URL", type: "url", maxLength: 300 },
      { key: "youtube_url", label: "YouTube URL", type: "url", maxLength: 300 },
      { key: "tiktok_url", label: "TikTok URL", type: "url", maxLength: 300 },
      { key: "x_url", label: "X (Twitter) URL", type: "url", maxLength: 300 },
      { key: "linkedin_url", label: "LinkedIn URL", type: "url", maxLength: 300 },
    ],
  },
];

export const SITE_SETTINGS_FIELDS = SITE_SETTINGS_GROUPS.flatMap((group) => group.fields);
export const SITE_SETTINGS_KEYS = SITE_SETTINGS_FIELDS.map((f) => f.key);

export function pickSiteSettings(data) {
  return Object.fromEntries(SITE_SETTINGS_KEYS.map((key) => [key, data?.[key] ?? ""]));
}
