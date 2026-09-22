"use client";

import { useState } from "react";
import { FiEye, FiEyeOff } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";

const EMPTY = { current_password: "", new_password: "", confirm_password: "" };

// The password-related input pattern (relative wrapper + right-aligned show/hide toggle) already established in
// component/auth/AuthForm.jsx, reused here instead of a second version.
function PasswordField({ id, label, placeholder, value, onChange, autoComplete }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={visible ? "text" : "password"}
          placeholder={placeholder}
          autoComplete={autoComplete}
          value={value}
          onChange={onChange}
          className="checkout-input w-full rounded-lg px-3 py-2.5 pr-9 text-sm"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          className="showcase-muted absolute right-2.5 top-1/2 -translate-y-1/2"
        >
          {visible ? <FiEyeOff className="h-4 w-4" aria-hidden="true" /> : <FiEye className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>
    </div>
  );
}

// "Change Password": posts to the EXISTING /auth/password/change/ endpoint (via the /api/account/change-password
// proxy), which already requires the current password and validates the new one with the backend's own password
// validators — this form only does cheap client-side checks (empty / too short / mismatch) for instant feedback;
// the backend stays the final authority and whatever it rejects is shown verbatim as a toast. On success the
// proxy has already rotated this session's httpOnly cookies to the fresh token pair the backend issued (it
// blacklists every other session), so nothing here needs to touch tokens or force a logout.
export default function ChangePasswordForm() {
  const [values, setValues] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const set = (key) => (e) => setValues((v) => ({ ...v, [key]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    if (saving) return;

    if (!values.current_password) {
      notify.error("Please enter your current password.");
      return;
    }
    if (values.new_password.length < 8) {
      notify.error("Password must be at least 8 characters.");
      return;
    }
    if (values.new_password !== values.confirm_password) {
      notify.error("Passwords do not match.");
      return;
    }

    setSaving(true);
    try {
      const res = await fetch("/api/account/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password: values.current_password, new_password: values.new_password }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to change your password. Please try again."));
        return;
      }
      setValues(EMPTY);
      notify.success("Password changed successfully.");
    } catch {
      notify.error("Unable to change your password. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="dashboard-card flex w-full flex-col gap-4 rounded-2xl p-5 sm:p-6">
      <h2 className="custom-font text-xl">Change Password</h2>

      <PasswordField
        id="account-current-password"
        label="Current Password"
        placeholder="Enter current password"
        autoComplete="current-password"
        value={values.current_password}
        onChange={set("current_password")}
      />
      <PasswordField
        id="account-new-password"
        label="New Password"
        placeholder="Enter new password"
        autoComplete="new-password"
        value={values.new_password}
        onChange={set("new_password")}
      />
      <PasswordField
        id="account-confirm-password"
        label="Confirm Password"
        placeholder="Confirm new password"
        autoComplete="new-password"
        value={values.confirm_password}
        onChange={set("confirm_password")}
      />

      <button type="submit" disabled={saving} className="auth-btn auth-btn--primary self-start rounded-full px-8 py-2.5 text-sm font-medium">
        {saving ? "Changing Password..." : "Change Password"}
      </button>
    </form>
  );
}
