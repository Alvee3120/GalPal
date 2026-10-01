"use client";

import { useState } from "react";
import { FiAlertCircle, FiSave } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { SITE_SETTINGS_GROUPS, SITE_SETTINGS_KEYS } from "@/lib/siteSettingsAdmin";

const trimmed = (values) => Object.fromEntries(SITE_SETTINGS_KEYS.map((key) => [key, String(values[key] ?? "").trim()]));
const same = (a, b) => SITE_SETTINGS_KEYS.every((key) => String(a[key] ?? "").trim() === String(b[key] ?? "").trim());

// Admin → Site Settings: the store's name, contact details, support hours and social links (the one Site Settings
// record). The footer and every invoice read these; a blank field is simply not shown there.
export default function SiteSettingsForm({ initial }) {
  const [saved, setSaved] = useState(initial);
  const [values, setValues] = useState(initial);
  const [saving, setSaving] = useState(false);

  if (!initial) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="custom-font text-2xl sm:text-3xl">Site Settings</h1>
        <div className="dashboard-card flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <FiAlertCircle className="h-8 w-8" aria-hidden="true" />
          <p className="text-sm">Unable to load the site settings. Please refresh the page.</p>
        </div>
      </div>
    );
  }

  const dirty = !same(values, saved);

  async function save(event) {
    event.preventDefault();
    const body = trimmed(values);
    if (!body.site_name) return notify.error("Store Name is required.");
    setSaving(true);
    let res;
    try {
      const r = await fetch("/api/admin/site-settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
        body: JSON.stringify(body),
      });
      res = { ok: r.ok, status: r.status, data: await r.json().catch(() => null) };
    } catch {
      res = { ok: false, status: 0, data: null };
    }
    setSaving(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to save the site settings."));
    setSaved(res.data);
    setValues(res.data);
    notify.success("Site settings saved.");
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="custom-font text-2xl sm:text-3xl">Site Settings</h1>
        <p className="showcase-muted text-sm">Your store&apos;s details, shown in the site footer and on invoices.</p>
      </div>

      <form onSubmit={save} className="flex w-full flex-col gap-6">
        {SITE_SETTINGS_GROUPS.map((group) => (
          <section key={group.title} className="dashboard-card rounded-2xl p-5 sm:p-6">
            <div>
              <h2 className="custom-font text-lg font-bold">{group.title}</h2>
              {group.note && <p className="showcase-muted mt-1 text-xs">{group.note}</p>}
            </div>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {group.fields.map((field) => {
                const id = `site-${field.key}`;
                const common = {
                  id,
                  value: values[field.key] ?? "",
                  maxLength: field.maxLength,
                  required: field.required,
                  onChange: (e) => setValues((v) => ({ ...v, [field.key]: e.target.value })),
                  className: "checkout-input w-full rounded-lg px-3 py-2.5 text-sm",
                };
                return (
                  <div key={field.key} className={`flex min-w-0 flex-col gap-1.5 ${field.type === "textarea" || field.wide ? "sm:col-span-2" : ""}`}>
                    <label htmlFor={id} className="text-sm font-medium">
                      {field.label}
                      {field.required && <span aria-hidden="true"> *</span>}
                    </label>
                    {field.type === "textarea" ? (
                      <textarea {...common} rows={3} />
                    ) : (
                      <input {...common} type={field.type} autoComplete="off" placeholder={field.type === "url" ? "https://" : undefined} />
                    )}
                    {field.hint && <p className="showcase-muted text-xs">{field.hint}</p>}
                  </div>
                );
              })}
            </div>
          </section>
        ))}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saving || !dirty}
            className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-medium"
          >
            <FiSave className="h-4 w-4" aria-hidden="true" />
            {saving ? "Saving…" : "Save Settings"}
          </button>
          {dirty && <span className="showcase-muted text-xs">Unsaved changes</span>}
        </div>
      </form>
    </div>
  );
}
