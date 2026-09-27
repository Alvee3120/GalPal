"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FiEye, FiEyeOff } from "react-icons/fi";
import { forgotPasswordAction, resetPasswordAction } from "@/app/actions/auth";
import { notify } from "@/lib/notify";

const RESEND_SECONDS = 60; // the backend's PASSWORD_RESET_OTP_RESEND_COOLDOWN_SECONDS default
// What the backend's validate_password (AUTH_PASSWORD_VALIDATORS) checks on a reset, in Django's own words.
const RULES = [
  "Your password must contain at least 8 characters.",
  "Your password can't be a commonly used password.",
  "Your password can't be entirely numeric.",
];
const INPUT = "auth-input w-full py-[clamp(0.3rem,1.3dvh,0.875rem)] text-sm";
const BUTTON = "auth-btn auth-btn--primary w-full rounded-full px-6 text-sm font-medium py-[clamp(0.4rem,1.5dvh,0.75rem)]";

function PasswordField({ id, label, value, onChange, shown, onToggle, autoComplete, invalid, describedBy }) {
  return (
    <div>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={shown ? "text" : "password"}
          placeholder={label}
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className={`${INPUT} pr-8`}
        />
        <button
          type="button"
          onClick={onToggle}
          aria-label={shown ? "Hide password" : "Show password"}
          aria-pressed={shown}
          className="auth-link absolute right-0 top-1/2 -translate-y-1/2 p-1 no-underline"
        >
          {shown ? <FiEyeOff className="h-4 w-4" aria-hidden="true" /> : <FiEye className="h-4 w-4" aria-hidden="true" />}
        </button>
      </div>
    </div>
  );
}

// Forgot password, on the backend's EXISTING code-based reset (apps.accounts: /auth/password/forgot/ then
// /auth/password/reset/ — a 6-digit code sent by email or SMS, not a link). Step 1 asks for the email or phone and
// requests a code; step 2 takes the code and the new password. The email/phone and code live only in this page's
// state (never stored), and nothing here decides whether a code is valid — the backend does.
export default function ForgotPasswordFlow() {
  const router = useRouter();
  const [step, setStep] = useState("request"); // "request" | "reset"
  const [identifier, setIdentifier] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [shown, setShown] = useState(false);
  const [pending, setPending] = useState(false);
  const [codeInvalid, setCodeInvalid] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const mismatch = confirm.length > 0 && password !== confirm;

  async function requestCode(e) {
    e?.preventDefault();
    if (pending) return;
    if (!identifier.trim()) return notify.error("Please enter your email or phone number.");
    setPending(true);
    const result = await forgotPasswordAction(identifier);
    setPending(false);
    if (!result.ok) return notify.error(result.error);
    notify.success(result.message);
    setCodeInvalid(false);
    setCode("");
    setCooldown(RESEND_SECONDS);
    setStep("reset");
  }

  async function resetPassword(e) {
    e.preventDefault();
    if (pending) return;
    if (!/^\d{6}$/.test(code.trim())) return notify.error("Enter the 6-digit code we sent you.");
    if (!password) return notify.error("Please choose a new password.");
    if (password !== confirm) return notify.error("Passwords do not match.");
    setPending(true);
    const result = await resetPasswordAction({ identifier, otp: code, newPassword: password });
    setPending(false);
    if (!result.ok) {
      if (result.invalidCode) setCodeInvalid(true);
      return notify.error(result.invalidCode ? "This reset code is invalid or has expired." : result.error);
    }
    setPassword("");
    setConfirm("");
    notify.success(result.message);
    router.push("/login");
  }

  if (step === "request") {
    return (
      <>
        <h2 className="custom-font text-[clamp(1.125rem,3.4dvh,1.875rem)] leading-tight">Forgot Password</h2>
        <p className="auth-muted mt-2 text-sm">Enter your email address  and we&apos;ll send you a code to reset your password.</p>
        <form onSubmit={requestCode} noValidate className="mt-[clamp(0.5rem,2.4dvh,1.75rem)] flex flex-col gap-[clamp(0.5rem,2dvh,1.5rem)]">
          <div>
            <label htmlFor="forgot-identifier" className="sr-only">
              Email 
            </label>
            <input
              id="forgot-identifier"
              type="text"
              inputMode="email"
              autoComplete="username"
              placeholder="Email "
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className={INPUT}
            />
          </div>
          <button type="submit" disabled={pending} className={BUTTON}>
            {pending ? "Sending..." : "Send Reset Code"}
          </button>
        </form>
        <p className="auth-muted mt-[clamp(0.5rem,1.6dvh,1.25rem)] text-center text-xs">
          <Link href="/login" className="auth-link font-medium">
            Back to Login
          </Link>
        </p>
      </>
    );
  }

  return (
    <>
      <h2 className="custom-font text-[clamp(1.125rem,3.4dvh,1.875rem)] leading-tight">Reset Password</h2>
      <p className="auth-muted mt-2 text-sm">
        If an account exists for <span className="font-medium">{identifier.trim()}</span>, we&apos;ve sent it a 6-digit code on your mail. It expires in 10 minutes.
      </p>

      {codeInvalid && (
        <div role="alert" className="auth-error mt-3 text-xs">
          This reset code is invalid or has expired.{" "}
          <button type="button" onClick={requestCode} disabled={pending || cooldown > 0} className="auth-link font-medium underline disabled:no-underline disabled:opacity-60">
            {cooldown > 0 ? `Request a new code in ${cooldown}s` : "Request a new code"}
          </button>
        </div>
      )}

      <form onSubmit={resetPassword} noValidate className="mt-[clamp(0.5rem,2dvh,1.25rem)] flex flex-col gap-[clamp(0.5rem,1.8dvh,1.25rem)]">
        <div>
          <label htmlFor="reset-code" className="sr-only">
            Reset code
          </label>
          <input
            id="reset-code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            placeholder="6-digit code"
            value={code}
            onChange={(e) => {
              setCode(e.target.value.replace(/\D/g, "").slice(0, 6));
              setCodeInvalid(false);
            }}
            aria-invalid={codeInvalid || undefined}
            className={`${INPUT} tracking-[0.3em]`}
          />
        </div>
        <PasswordField
          id="reset-password"
          label="New Password"
          value={password}
          onChange={setPassword}
          shown={shown}
          onToggle={() => setShown((s) => !s)}
          autoComplete="new-password"
          describedBy="reset-rules"
        />
        <PasswordField
          id="reset-confirm"
          label="Password Confirmation"
          value={confirm}
          onChange={setConfirm}
          shown={shown}
          onToggle={() => setShown((s) => !s)}
          autoComplete="new-password"
          invalid={mismatch}
          describedBy={mismatch ? "reset-mismatch" : undefined}
        />
        {mismatch && (
          <p id="reset-mismatch" role="alert" className="auth-error -mt-1 text-xs">
            Passwords do not match.
          </p>
        )}
        <ul id="reset-rules" className="auth-muted -mt-1 list-disc space-y-0.5 pl-4 text-[0.7rem] leading-snug">
          {RULES.map((rule) => (
            <li key={rule}>{rule}</li>
          ))}
        </ul>
        <button type="submit" disabled={pending} className={BUTTON}>
          {pending ? "Resetting..." : "Reset Password"}
        </button>
      </form>

      <div className="auth-muted mt-[clamp(0.5rem,1.6dvh,1.25rem)] flex flex-wrap items-center justify-between gap-2 text-xs">
        <button type="button" onClick={requestCode} disabled={pending || cooldown > 0} className="auth-link font-medium disabled:opacity-60">
          {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
        </button>
        <button
          type="button"
          onClick={() => {
            setStep("request");
            setCodeInvalid(false);
          }}
          className="auth-link font-medium"
        >
          Use a different email or phone
        </button>
        <Link href="/login" className="auth-link font-medium">
          Back to Login
        </Link>
      </div>
    </>
  );
}
