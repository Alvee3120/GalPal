"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FiCheck, FiCopy, FiEye, FiEyeOff, FiKey } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { errorText } from "@/lib/productAdmin";
import { isValidBdPhone, normalizeBdPhone } from "@/lib/phone";
import { PASSWORD_RULES, USER_ROLES, generateTemporaryPassword, userFetch } from "@/lib/userAdmin";
import { formatOrderDateTime } from "@/lib/orderStatus";
import ConfirmDialog from "@/component/shared/ConfirmDialog";
import Modal from "@/component/shared/Modal";
import { SingleImageInput } from "../products/ImageInputs";

const INPUT = "checkout-input rounded-lg px-3 py-2.5 text-sm";

function PasswordInput({ id, value, onChange, autoComplete, invalid, describedBy }) {
  const [shown, setShown] = useState(false);
  return (
    <div className="relative">
      <input
        id={id}
        type={shown ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        className={`${INPUT} w-full pr-11`}
      />
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? "Hide password" : "Show password"}
        title={shown ? "Hide password" : "Show password"}
        className="showcase-muted absolute right-2 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full hover:text-current"
      >
        {shown ? <FiEyeOff className="h-4 w-4" aria-hidden="true" /> : <FiEye className="h-4 w-4" aria-hidden="true" />}
      </button>
    </div>
  );
}

// Add / Edit User over POST and PATCH /admin/users/ (apps.accounts — IsAdmin). The backend is the authority for every
// rule: phone format and uniqueness, allowed roles, and the password (Django's AUTH_PASSWORD_VALIDATORS — similarity to
// the name/phone, length, common passwords, all-numeric), plus "not your own role/activation" and "always one active
// admin". The checks here only catch the obvious before a request. Passwords are never prefilled or kept after saving,
// and a user's current password can't be shown — only a hash is stored. "Reset Password" instead sets a new temporary
// one (made here, shown to the admin once) that the user must change at their next login.
export default function UserForm({ user = null, isSelf = false }) {
  const router = useRouter();
  const isEdit = Boolean(user);

  const [phone, setPhone] = useState(user?.phone ?? "");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [role, setRole] = useState(user?.role ?? "customer");
  const [isActive, setIsActive] = useState(user?.is_active ?? true);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [avatar, setAvatar] = useState({ url: user?.avatar ?? null, file: null, removed: false });
  const [submitting, setSubmitting] = useState(false);
  const [resetAsk, setResetAsk] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [tempPassword, setTempPassword] = useState(null); // shown once in a dialog, then dropped
  const [copied, setCopied] = useState(false);

  const mismatch = confirm.length > 0 && password !== confirm;

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    if (!isValidBdPhone(phone)) return notify.error("Please enter a valid phone number, e.g. 01712345678.");
    if (!fullName.trim()) return notify.error("Full name is required.");
    const changingPassword = !isEdit || password || confirm;
    if (changingPassword) {
      if (!password) return notify.error("Password is required.");
      if (password !== confirm) return notify.error("Passwords do not match.");
    }

    const fields = { phone: normalizeBdPhone(phone), full_name: fullName.trim(), role };
    if (isEdit) fields.is_active = isActive;
    if (changingPassword) Object.assign(fields, { password, password_confirm: confirm });
    // With a new or removed avatar the request is multipart (the image travels with it); otherwise plain JSON.
    let body = fields;
    if (avatar.file || avatar.removed) {
      body = new FormData();
      for (const [key, value] of Object.entries(fields)) body.append(key, String(value));
      body.append("avatar", avatar.file ?? ""); // "" clears it
    }

    setSubmitting(true);
    const res = await userFetch(isEdit ? `/${user.id}` : "", { method: isEdit ? "PATCH" : "POST", body });
    if (!res.ok) {
      setSubmitting(false);
      return notify.error(errorText(res, isEdit ? "Unable to update the user. Please try again." : "Unable to create the user. Please try again."));
    }
    setPassword("");
    setConfirm("");
    notify.success(isEdit ? "User updated successfully." : "User created successfully.");
    router.push("/dashboard/admin/users");
    router.refresh();
  }

  async function resetPassword() {
    if (resetting) return;
    setResetting(true);
    const temporary = generateTemporaryPassword();
    const res = await userFetch(`/${user.id}`, {
      method: "PATCH",
      body: { password: temporary, password_confirm: temporary, must_change_password: true },
    });
    setResetting(false);
    setResetAsk(false);
    if (!res.ok) return notify.error(errorText(res, "Unable to reset the password. Please try again."));
    notify.success("Password reset successfully.");
    setCopied(false);
    setTempPassword(temporary);
  }

  async function copyTemporary() {
    try {
      await navigator.clipboard.writeText(tempPassword);
      setCopied(true);
    } catch {
      notify.error("Couldn't copy. Please select the password and copy it.");
    }
  }

  function closeTemporary() {
    setTempPassword(null);
    setCopied(false);
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-6">
      {isEdit && (
        // Read-only account facts from GET /admin/users/<id>/. Nothing here is a form field or sent on save:
        // created_at is the account's creation time, last_login is written only by a successful login
        // (apps.accounts.services.record_login) and is null until the user has logged in once.
        <section className="dashboard-card rounded-2xl p-5 sm:p-6" aria-labelledby="uf-info-title">
          <h2 id="uf-info-title" className="custom-font text-lg">
            Account Information
          </h2>
          <div className="mt-4 flex flex-col gap-5 sm:flex-row sm:items-start">
            <div className="shrink-0">
              <SingleImageInput id="uf-avatar" label="Avatar" clearable compact value={avatar} onChange={setAvatar} />
            </div>
            <dl className="grid flex-1 grid-cols-1 gap-x-6 gap-y-3 text-sm min-[480px]:grid-cols-2">
              <div>
                <dt className="showcase-muted text-xs">Created via Checkout</dt>
                <dd className="mt-0.5 font-medium">{user.created_via_checkout ? "Yes" : "No"}</dd>
              </div>
              <div>
                <dt className="showcase-muted text-xs">Email</dt>
                <dd className="mt-0.5 break-all font-medium">{user.email || "—"}</dd>
              </div>
              <div>
                <dt className="showcase-muted text-xs">
                  Created At <span className="read-only-tag ml-1 rounded px-1.5 py-0.5 text-[0.625rem] font-medium">Read only</span>
                </dt>
                <dd className="mt-0.5 font-medium">{formatOrderDateTime(user.created_at)}</dd>
              </div>
              <div>
                <dt className="showcase-muted text-xs">
                  Last Login <span className="read-only-tag ml-1 rounded px-1.5 py-0.5 text-[0.625rem] font-medium">Read only</span>
                </dt>
                <dd className="mt-0.5 font-medium">{user.last_login ? formatOrderDateTime(user.last_login) : "Never"}</dd>
              </div>
            </dl>
          </div>
          {!isSelf && (
            <div className="mt-5 flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="showcase-muted text-xs">
                Passwords are stored encrypted, so the current one can&apos;t be shown. Reset it to give the user a new temporary
                password — they&apos;ll be asked to change it when they next log in.
                {user.must_change_password && <span className="mt-1 block font-medium">A password change is pending for this user.</span>}
              </p>
              <button
                type="button"
                onClick={() => setResetAsk(true)}
                className="auth-btn auth-btn--outline inline-flex shrink-0 items-center gap-2 rounded-full px-4 py-2 text-sm font-medium"
              >
                <FiKey className="h-4 w-4" aria-hidden="true" />
                Reset Password
              </button>
            </div>
          )}
        </section>
      )}

      <section className="dashboard-card rounded-2xl p-5 sm:p-6">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {!isEdit && (
            <div className="sm:col-span-2">
              <SingleImageInput id="uf-avatar" label="Avatar (Optional)" clearable compact value={avatar} onChange={setAvatar} />
            </div>
          )}
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="uf-phone" className="text-sm font-medium">
              Phone <span aria-hidden="true">*</span>
            </label>
            <input
              id="uf-phone"
              type="tel"
              inputMode="tel"
              autoComplete="off"
              placeholder="01712345678"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className={INPUT}
            />
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="uf-name" className="text-sm font-medium">
              Full name <span aria-hidden="true">*</span>
            </label>
            <input id="uf-name" type="text" maxLength={150} autoComplete="off" value={fullName} onChange={(e) => setFullName(e.target.value)} className={INPUT} />
          </div>

          <div className="flex min-w-0 flex-col gap-1.5">
            <label htmlFor="uf-role" className="text-sm font-medium">
              Role <span aria-hidden="true">*</span>
            </label>
            <select id="uf-role" value={role} onChange={(e) => setRole(e.target.value)} disabled={isSelf} className={INPUT}>
              {USER_ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
            {isSelf && <p className="showcase-muted text-xs">You can&apos;t change your own role.</p>}
          </div>

          {isEdit && (
            <div className="flex flex-col justify-center gap-1.5">
              <span className="text-sm font-medium">Is Active</span>
              <label htmlFor="uf-active" className="flex cursor-pointer items-start gap-2.5 text-sm">
                <input
                  id="uf-active"
                  type="checkbox"
                  checked={isActive}
                  disabled={isSelf}
                  onChange={(e) => setIsActive(e.target.checked)}
                  className="form-check mt-0.5 h-4 w-4 shrink-0"
                />
                <span>
                  {isActive ? "Active" : "Inactive"}
                  <span className="showcase-muted block text-xs">
                    {isSelf ? "You can't deactivate your own account." : "An inactive user can't log in."}
                  </span>
                </span>
              </label>
            </div>
          )}

          <div className="flex min-w-0 flex-col gap-1.5 sm:col-span-2">
            <label htmlFor="uf-password" className="text-sm font-medium">
              Password {isEdit ? <span className="showcase-muted font-normal">(leave empty to keep the current password)</span> : <span aria-hidden="true">*</span>}
            </label>
            <PasswordInput id="uf-password" value={password} onChange={setPassword} autoComplete="new-password" describedBy="uf-password-rules" />
            <div id="uf-password-rules" className="password-rules rounded-lg px-3 py-2.5 text-xs">
              <p className="font-medium">Password requirements:</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                {PASSWORD_RULES.map((rule) => (
                  <li key={rule}>{rule}</li>
                ))}
              </ul>
            </div>
          </div>

          <div className="flex min-w-0 flex-col gap-1.5 sm:col-span-2">
            <label htmlFor="uf-confirm" className="text-sm font-medium">
              Password confirmation {!isEdit && <span aria-hidden="true">*</span>}
            </label>
            <PasswordInput
              id="uf-confirm"
              value={confirm}
              onChange={setConfirm}
              autoComplete="new-password"
              invalid={mismatch}
              describedBy={mismatch ? "uf-confirm-error" : undefined}
            />
            {mismatch && (
              <p id="uf-confirm-error" role="alert" className="field-error text-xs">
                Passwords do not match.
              </p>
            )}
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-end gap-3">
        <Link href="/dashboard/admin/users" className="auth-btn auth-btn--outline rounded-full px-6 py-2.5 text-sm font-medium">
          Cancel
        </Link>
        <button type="submit" disabled={submitting} aria-busy={submitting} className="auth-btn auth-btn--primary rounded-full px-6 py-2.5 text-sm font-medium">
          {submitting ? (isEdit ? "Saving User..." : "Creating User...") : isEdit ? "Save Changes" : "Create User"}
        </button>
      </div>

      {isEdit && (
        <>
          <ConfirmDialog
            open={resetAsk}
            title="Reset Password?"
            description={`${user.full_name || user.phone} will get a new temporary password, be logged out everywhere, and have to choose a new password at their next login.`}
            confirmLabel="Reset Password"
            busyLabel="Resetting..."
            busy={resetting}
            onConfirm={resetPassword}
            onCancel={() => !resetting && setResetAsk(false)}
          />
          <Modal open={Boolean(tempPassword)} title="Temporary Password" onClose={closeTemporary}>
            {tempPassword && (
              <div className="flex flex-col gap-4 text-sm">
                <p className="showcase-muted">
                  Share this with {user.full_name || user.phone}. It&apos;s shown only once — after you close this, it can&apos;t be seen
                  again.
                </p>
                <div className="temp-password flex items-center justify-between gap-3 rounded-lg px-3 py-2.5">
                  <code className="select-all break-all font-mono text-base">{tempPassword}</code>
                  <button
                    type="button"
                    onClick={copyTemporary}
                    title={copied ? "Copied" : "Copy password"}
                    aria-label={copied ? "Copied" : "Copy password"}
                    className="icon-action flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
                  >
                    {copied ? <FiCheck className="h-4 w-4" aria-hidden="true" /> : <FiCopy className="h-4 w-4" aria-hidden="true" />}
                  </button>
                </div>
                <p className="showcase-muted text-xs">They&apos;ll be asked to set their own password when they log in with it.</p>
                <button type="button" onClick={closeTemporary} className="auth-btn auth-btn--primary self-end rounded-full px-5 py-2 text-sm font-medium">
                  Done
                </button>
              </div>
            )}
          </Modal>
        </>
      )}
    </form>
  );
}
