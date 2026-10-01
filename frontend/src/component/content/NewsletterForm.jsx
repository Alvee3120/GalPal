"use client";

import { useState } from "react";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";

// Footer newsletter sign-up: one box that takes an email or a Bangladeshi mobile number (POST /newsletter/subscribe/
// via /api/newsletter/subscribe). The reply is the same for new and existing subscribers.
export default function NewsletterForm() {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    const contact = value.trim();
    if (!contact) return notify.error("Enter your email or phone number.");
    const body = contact.includes("@") ? { email: contact } : { phone: contact };
    setBusy(true);
    try {
      const res = await fetch("/api/newsletter/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...body, source: "footer" }),
        cache: "no-store",
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Couldn't subscribe. Please try again."));
        return;
      }
      setDone(true);
      setValue("");
    } catch {
      notify.error("Couldn't subscribe. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (done) return <p className="mt-6 text-sm font-medium">Thanks! You&apos;re subscribed to our updates and offers.</p>;

  return (
    <form onSubmit={onSubmit} className="mt-6 max-w-sm">
      <label htmlFor="newsletter-contact" className="text-sm font-semibold">
        Get offers &amp; new arrivals
      </label>
      <div className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-2">
        <input
          id="newsletter-contact"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          maxLength={254}
          autoComplete="email"
          placeholder="Email or phone number"
          className="checkout-input w-full rounded-full px-4 py-2.5 text-sm"
        />
        <button type="submit" disabled={busy} className="auth-btn auth-btn--primary rounded-full px-5 py-2.5 text-sm font-medium">
          {busy ? "…" : "Subscribe"}
        </button>
      </div>
    </form>
  );
}
