"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FcGoogle } from "react-icons/fc";
import { FiEye, FiEyeOff } from "react-icons/fi";
import { loginAction, registerAction } from "@/app/actions/auth";
import { notify } from "@/lib/notify";

const CONFIG = {
  register: {
    title: "Create a account",
    submit: "Sign up",
    pending: "Creating account...",
    action: registerAction,
    fields: [
      { name: "full_name", type: "text", placeholder: "Enter your name", autoComplete: "name" },
      { name: "phone", type: "tel", placeholder: "Enter your mobile number", autoComplete: "tel" },
      { name: "email", type: "email", placeholder: "Enter your email (optional)", autoComplete: "email", optional: true },
      { name: "password", type: "password", placeholder: "Password", autoComplete: "new-password" },
    ],
    switchText: "Already have an account?",
    switchLabel: "Log in",
    switchHref: "/login",
  },
  login: {
    title: "Welcome back",
    submit: "Log in",
    pending: "Logging in...",
    action: loginAction,
    fields: [
      { name: "identifier", type: "text", placeholder: "Phone number or email", autoComplete: "username" },
      { name: "password", type: "password", placeholder: "Password", autoComplete: "current-password" },
    ],
    switchText: "New to GalPal?",
    switchLabel: "Create an account",
    switchHref: "/register",
  },
};

const initialState = { error: "", fieldErrors: {}, values: {} };

export default function AuthForm({ mode }) {
  const cfg = CONFIG[mode];
  const [state, formAction, pending] = useActionState(cfg.action, initialState);
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();
  const handled = useRef(null);

  // Every result is announced once through the global toast: success -> toast, then go where the action says
  // (login: home/account, register: login page); failure -> error toast and stay on the page.
  useEffect(() => {
    if (state === initialState || handled.current === state) return;
    handled.current = state;
    if (state.success) {
      notify.success(state.message);
      router.push(state.redirectTo);
    } else if (state.error) {
      notify.error(state.error);
    }
  }, [state, router]);

  return (
    <>
      <h2 className="custom-font text-[clamp(1.125rem,3.4dvh,1.875rem)] leading-tight">{cfg.title}</h2>

      <form action={formAction} noValidate className="mt-[clamp(0.5rem,2.4dvh,1.75rem)] flex flex-col gap-[clamp(0.5rem,2dvh,1.5rem)]">
        {/* On very short (landscape) screens the fields sit two per row so nothing is hidden. */}
        <div className="grid gap-x-4 gap-y-[clamp(0.5rem,2dvh,1.5rem)] [@media(max-height:480px)]:grid-cols-2">
        {cfg.fields.map((f) => {
          const error = state.fieldErrors?.[f.name];
          const isPassword = f.type === "password";
          return (
            <div key={f.name}>
              <label htmlFor={`${mode}-${f.name}`} className="sr-only">
                {f.placeholder}
              </label>
              <div className="relative">
              <input
                id={`${mode}-${f.name}`}
                name={f.name}
                type={isPassword && showPassword ? "text" : f.type}
                placeholder={f.placeholder}
                autoComplete={f.autoComplete}
                defaultValue={isPassword ? undefined : state.values?.[f.name] ?? ""}
                required={!f.optional}
                aria-invalid={error ? "true" : undefined}
                aria-describedby={error ? `${mode}-${f.name}-error` : undefined}
                className={`auth-input w-full py-[clamp(0.3rem,1.3dvh,0.875rem)] text-sm ${isPassword ? "pr-8" : ""}`}
              />
              {isPassword && (
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  className="auth-link absolute right-0 top-1/2 -translate-y-1/2 p-1 no-underline"
                >
                  {showPassword ? <FiEyeOff className="h-4 w-4" aria-hidden="true" /> : <FiEye className="h-4 w-4" aria-hidden="true" />}
                </button>
              )}
              </div>
              {error && (
                <p id={`${mode}-${f.name}-error`} role="alert" className="auth-error mt-0.5 text-[0.7rem] leading-tight sm:text-xs">
                  {error}
                </p>
              )}
            </div>
          );
        })}
        </div>

        <div className="flex flex-col gap-[clamp(0.375rem,1.4dvh,0.75rem)]">
          <button type="submit" disabled={pending} className={`auth-btn auth-btn--primary w-full rounded-full px-6 text-sm font-medium py-[clamp(0.4rem,1.5dvh,0.75rem)]`}>
            {pending ? cfg.pending : cfg.submit}
          </button>
          {/* No Google sign-in endpoint exists on the backend yet, so this stays disabled. */}
          <button
            type="button"
            disabled
            title="Google sign-in is coming soon"
            className={`auth-btn auth-btn--outline flex w-full items-center justify-center gap-2 rounded-full px-6 text-sm py-[clamp(0.4rem,1.5dvh,0.75rem)]`}
          >
            <FcGoogle className="h-4 w-4" aria-hidden="true" />
            Continue with Google
          </button>
        </div>
      </form>

      <p className="auth-muted mt-[clamp(0.5rem,1.6dvh,1.25rem)] text-center text-xs">
        {cfg.switchText}{" "}
        <Link href={cfg.switchHref} className="auth-link font-medium">
          {cfg.switchLabel}
        </Link>
      </p>
    </>
  );
}
