"use client";

import { useState } from "react";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";
import ChangePasswordForm from "./ChangePasswordForm";

// "My Account": the editable fields from the EXISTING profile API (full_name, email — phone/role are backend
// read-only, see ProfileSerializer.read_only_fields, so they're shown but not editable here), via the existing
// /api/account proxy (PATCH /account/profile/). Saved addresses are listed read-only; adding/editing addresses
// already happens at checkout (lib/checkoutAccount.js) — a dedicated address manager here is a further step.
export default function AccountForm({ initialProfile, addresses }) {
  const [profile, setProfile] = useState(initialProfile);
  const [values, setValues] = useState({ full_name: initialProfile.full_name, email: initialProfile.email ?? "" });
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (saving) return;
    if (!values.full_name.trim()) {
      notify.error("Please enter your full name.");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch("/api/account/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ full_name: values.full_name.trim(), email: values.email.trim() || null }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to update your account. Please try again."));
        return;
      }
      setProfile(data);
      notify.success("Account updated successfully.");
    } catch {
      notify.error("Unable to update your account. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <form onSubmit={handleSubmit} noValidate className="dashboard-card flex flex-col gap-4 rounded-2xl p-5 sm:p-6">
          <h2 className="custom-font text-xl">Profile</h2>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="account-name" className="text-sm font-medium">
              Full Name <span aria-hidden="true">*</span>
            </label>
            <input
              id="account-name"
              type="text"
              autoComplete="name"
              value={values.full_name}
              onChange={(e) => setValues((v) => ({ ...v, full_name: e.target.value }))}
              className="checkout-input rounded-lg px-3 py-2.5 text-sm"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="account-email" className="text-sm font-medium">
              Email <span className="showcase-muted font-normal">(Optional)</span>
            </label>
            <input
              id="account-email"
              type="email"
              autoComplete="email"
              value={values.email}
              onChange={(e) => setValues((v) => ({ ...v, email: e.target.value }))}
              className="checkout-input rounded-lg px-3 py-2.5 text-sm"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium">Phone Number</span>
            <p className="showcase-muted text-sm">{profile.phone}</p>
          </div>

          <button type="submit" disabled={saving} className="auth-btn auth-btn--primary self-start rounded-full px-8 py-2.5 text-sm font-medium">
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </form>

        <ChangePasswordForm />
      </div>

      <div>
        <h2 className="custom-font text-xl">Saved Addresses</h2>
        {addresses.length === 0 ? (
          <p className="showcase-muted mt-3 text-sm">No saved addresses yet — one is added automatically the next time you check out.</p>
        ) : (
          <ul className="mt-4 grid gap-3 sm:grid-cols-2">
            {addresses.map((address) => (
              <li key={address.id} className="dashboard-card rounded-2xl p-4 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-semibold">{address.label || "Address"}</p>
                  {address.is_default && <span className="product-card__chip rounded-full px-2 py-0.5 text-xs font-medium">Default</span>}
                </div>
                <p className="mt-1">{address.full_name}</p>
                <p className="showcase-muted">{address.phone}</p>
                <p className="showcase-muted mt-1">
                  {address.address_line}, {address.area ? `${address.area}, ` : ""}
                  {address.district}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
