"use server";

import { cookies } from "next/headers";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";

// Mirrors the backend's JWT lifetimes (15 min access, 7 day refresh).
const ACCESS_MAX_AGE = 60 * 15;
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7;

const GENERIC_ERROR = "Something went wrong. Please try again.";
const NETWORK_ERROR = "We couldn't reach the server. Please try again in a moment.";

async function callApi(path, body) {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json().catch(() => null);
    return { ok: res.ok, status: res.status, data };
  } catch {
    return { ok: false, status: 0, data: null, network: true };
  }
}

// Turns an API failure into { error, fieldErrors, values } where `error` is ALWAYS a short, user-friendly
// sentence (shown as a toast). Server/technical failures never leak through: 5xx and unparseable
// responses become a generic message; only the backend's own 4xx validation/auth text is passed on.
function toErrorState({ status, data, network }, values, fallback) {
  if (network) return { error: NETWORK_ERROR, fieldErrors: {}, values };

  const err = data?.error;
  const fieldErrors = {};
  for (const [field, messages] of Object.entries(err?.details ?? {})) {
    if (Array.isArray(messages)) fieldErrors[field] = messages.join(" ");
  }
  const firstFieldError = Object.values(fieldErrors)[0];

  let error;
  if (!err || status >= 500) error = GENERIC_ERROR;
  else if (err.code === "throttled") error = "Too many attempts. Please wait a moment and try again.";
  else if (firstFieldError) error = firstFieldError;
  else if (err.code === "validation_error") error = fallback;
  else error = typeof err.message === "string" && err.message.length <= 160 ? err.message : fallback;

  return { error, fieldErrors, values };
}

async function startSession({ access, refresh }) {
  const store = await cookies();
  const base = { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/" };
  store.set("access_token", access, { ...base, maxAge: ACCESS_MAX_AGE });
  store.set("refresh_token", refresh, { ...base, maxAge: REFRESH_MAX_AGE });
}

const text = (formData, key) => String(formData.get(key) ?? "").trim();

// Register: on success the account exists but the user is NOT signed in; the client shows a toast
// and sends them to the login page.
export async function registerAction(_prev, formData) {
  const values = { full_name: text(formData, "full_name"), phone: text(formData, "phone"), email: text(formData, "email") };
  const password = String(formData.get("password") ?? "");

  // Missing required fields are shown inline next to the inputs (no toast needed)
  const fieldErrors = {};
  if (!values.full_name) fieldErrors.full_name = "Please enter your name.";
  if (!values.phone) fieldErrors.phone = "Please enter your mobile number.";
  if (!password) fieldErrors.password = "Please choose a password.";
  if (Object.keys(fieldErrors).length) return { error: "", fieldErrors, values };

  const result = await callApi("/auth/register/", { ...values, email: values.email || null, password });
  if (!result.ok) return toErrorState(result, values, "Unable to create account. Please try again.");

  return { success: true, message: "Account created successfully!", redirectTo: "/login", error: "", fieldErrors: {}, values: {} };
}

// Login: on success the session cookies are set here; the client shows a toast, then navigates.
export async function loginAction(_prev, formData) {
  const values = { identifier: text(formData, "identifier") };
  const password = String(formData.get("password") ?? "");

  const fieldErrors = {};
  if (!values.identifier) fieldErrors.identifier = "Please enter your phone number or email.";
  if (!password) fieldErrors.password = "Please enter your password.";
  if (Object.keys(fieldErrors).length) return { error: "", fieldErrors, values };

  const result = await callApi("/auth/login/", { ...values, password });
  if (!result.ok) return toErrorState(result, values, "Invalid phone/email or password.");

  await startSession(result.data);
  return {
    success: true,
    message: "Login successful!",
    redirectTo: result.data.must_change_password ? "/account" : "/",
    error: "",
    fieldErrors: {},
    values: {},
  };
}

export async function logoutAction() {
  const store = await cookies();
  const refresh = store.get("refresh_token")?.value;
  // Blacklist the refresh token server-side; clear the session either way.
  if (refresh) await callApi("/auth/logout/", { refresh });
  store.delete("access_token");
  store.delete("refresh_token");
}
