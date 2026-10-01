"use client";

import { useState } from "react";
import { FiSend } from "react-icons/fi";
import { notify } from "@/lib/notify";
import { messageFor } from "@/lib/apiError";

const EMPTY = { name: "", phone: "", email: "", subject: "", message: "" };

// The public contact form (POST /api/contact -> apps.care). Messages land in Admin -> Support Inbox. A phone or an
// email is needed so the team can reply (the backend enforces this too).
export default function ContactForm() {
  const [values, setValues] = useState(EMPTY);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const set = (key) => (e) => setValues((v) => ({ ...v, [key]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    if (!values.name.trim() || !values.message.trim()) return notify.error("Please enter your name and a message.");
    if (!values.phone.trim() && !values.email.trim()) return notify.error("Please give us a phone number or an email so we can reply.");
    setSending(true);
    try {
      const res = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      const data = await res.json().catch(() => null);
      if (res.status === 429) return notify.error("You've sent several messages already. Please try again a little later.");
      if (!res.ok) return notify.error(messageFor({ status: res.status, details: data?.error?.details }, "Unable to send your message. Please try again."));
      setValues(EMPTY);
      setSent(true);
      notify.success("Thanks! Your message has been sent.");
    } catch {
      notify.error("Unable to send your message. Please try again.");
    } finally {
      setSending(false);
    }
  }

  const input = "checkout-input w-full rounded-lg px-3 py-2.5 text-sm";
  return (
    <section className="contact-card min-w-0 rounded-2xl p-6 sm:p-8" aria-labelledby="contact-form-title">
      <h2 id="contact-form-title" className="custom-font text-2xl">
        Send Us a Message
      </h2>
      <p className="showcase-muted mt-1 text-sm">We usually reply within one working day.</p>
      {sent && <p className="mt-3 text-sm font-medium">Message received — we&apos;ll be in touch soon.</p>}
      <form onSubmit={submit} noValidate className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="flex min-w-0 flex-col gap-1.5 text-sm">
          <span className="font-medium">
            Name <span aria-hidden="true">*</span>
          </span>
          <input value={values.name} onChange={set("name")} maxLength={150} autoComplete="name" required className={input} />
        </label>
        <label className="flex min-w-0 flex-col gap-1.5 text-sm">
          <span className="font-medium">Phone</span>
          <input type="tel" value={values.phone} onChange={set("phone")} maxLength={20} autoComplete="tel" placeholder="01XXXXXXXXX" className={input} />
        </label>
        <label className="flex min-w-0 flex-col gap-1.5 text-sm">
          <span className="font-medium">Email</span>
          <input type="email" value={values.email} onChange={set("email")} maxLength={254} autoComplete="email" className={input} />
        </label>
        <label className="flex min-w-0 flex-col gap-1.5 text-sm">
          <span className="font-medium">Subject</span>
          <input value={values.subject} onChange={set("subject")} maxLength={150} className={input} />
        </label>
        <label className="flex min-w-0 flex-col gap-1.5 text-sm sm:col-span-2">
          <span className="font-medium">
            Message <span aria-hidden="true">*</span>
          </span>
          <textarea value={values.message} onChange={set("message")} maxLength={5000} rows={5} required className={input} />
        </label>
        <p className="showcase-muted text-xs sm:col-span-2">Please give a phone number or an email so we can reply.</p>
        <div className="sm:col-span-2">
          <button type="submit" disabled={sending} className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-medium">
            <FiSend className="h-4 w-4" aria-hidden="true" />
            {sending ? "Sending…" : "Send Message"}
          </button>
        </div>
      </form>
    </section>
  );
}
