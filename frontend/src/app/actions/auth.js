"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://192.168.68.129:8000/api/v1";

// Mirrors the backend's JWT lifetimes (15 min access, 7 day refresh).
const ACCESS_MAX_AGE = 60 * 15;
const REFRESH_MAX_AGE = 60 * 60 * 24 * 7;

async function callApi(path, body) {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      cache: "no-store",
    });
    const data = await res.json().catch(() => null);
    return { ok: res.ok, data };
  } catch {
    return { ok: false, data: null, network: true };
  }
}

// Turns the API error envelope into { error, fieldErrors }.
function toErrorState({ data, network }, values) {
  if (network) {
    return { error: "We couldn't reach the server. Please try again in a moment.", fieldErrors: {}, values };
  }
  const err = data?.error;
  const fieldErrors = {};
  for (const [field, messages] of Object.entries(err?.details ?? {})) {
    if (Array.isArray(messages)) fieldErrors[field] = messages.join(" ");
  }
  const hasFieldErrors = Object.keys(fieldErrors).length > 0;
  return {
    error: hasFieldErrors ? "" : err?.message ?? "Something went wrong. Please try again.",
    fieldErrors,
    values,
  };
}

async function startSession({ access, refresh }) {
  const store = await cookies();
  const base = { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/" };
  store.set("access_token", access, { ...base, maxAge: ACCESS_MAX_AGE });
  store.set("refresh_token", refresh, { ...base, maxAge: REFRESH_MAX_AGE });
}

const text = (formData, key) => String(formData.get(key) ?? "").trim();

export async function registerAction(_prev, formData) {
  const values = { full_name: text(formData, "full_name"), phone: text(formData, "phone"), email: text(formData, "email") };
  const password = String(formData.get("password") ?? "");

  const fieldErrors = {};
  if (!values.full_name) fieldErrors.full_name = "Please enter your name.";
  if (!values.phone) fieldErrors.phone = "Please enter your mobile number.";
  if (!password) fieldErrors.password = "Please choose a password.";
  if (Object.keys(fieldErrors).length) return { error: "", fieldErrors, values };

  const result = await callApi("/auth/register/", { ...values, email: values.email || null, password });
  if (!result.ok) return toErrorState(result, values);

  await startSession(result.data);
  redirect("/");
}

export async function loginAction(_prev, formData) {
  const values = { identifier: text(formData, "identifier") };
  const password = String(formData.get("password") ?? "");

  const fieldErrors = {};
  if (!values.identifier) fieldErrors.identifier = "Please enter your phone number or email.";
  if (!password) fieldErrors.password = "Please enter your password.";
  if (Object.keys(fieldErrors).length) return { error: "", fieldErrors, values };

  const result = await callApi("/auth/login/", { ...values, password });
  if (!result.ok) return toErrorState(result, values);

  await startSession(result.data);
  redirect(result.data.must_change_password ? "/account" : "/");
}

export async function logoutAction() {
  const store = await cookies();
  const refresh = store.get("refresh_token")?.value;
  // Blacklist the refresh token server-side; clear the session either way.
  if (refresh) await callApi("/auth/logout/", { refresh });
  store.delete("access_token");
  store.delete("refresh_token");
}
