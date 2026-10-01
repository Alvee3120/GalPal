"use client";

import { useState } from "react";
import Link from "next/link";

export default function UnsubscribeConfirm({ token }) {
  const [state, setState] = useState(token ? "ask" : "invalid"); // ask | busy | done | invalid | error

  async function confirm() {
    setState("busy");
    try {
      const res = await fetch("/api/newsletter/unsubscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
        cache: "no-store",
      });
      setState(res.ok ? "done" : res.status === 404 ? "invalid" : "error");
    } catch {
      setState("error");
    }
  }

  if (state === "done") {
    return <p>You&apos;ve been unsubscribed. You won&apos;t receive our newsletter any more.</p>;
  }
  if (state === "invalid") {
    return (
      <p>
        This unsubscribe link isn&apos;t valid. If you keep receiving messages, please <Link href="/contact" className="underline">contact us</Link>.
      </p>
    );
  }
  return (
    <div className="flex flex-col items-center gap-4">
      <p>Stop receiving GalPal offers and updates?</p>
      {state === "error" && <p className="text-sm">Something went wrong. Please try again.</p>}
      <button type="button" onClick={confirm} disabled={state === "busy"} className="auth-btn auth-btn--primary rounded-full px-6 py-3 text-sm font-medium">
        {state === "busy" ? "Unsubscribing…" : "Unsubscribe"}
      </button>
    </div>
  );
}
