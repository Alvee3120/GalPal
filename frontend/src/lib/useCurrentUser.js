"use client";

import { useEffect, useState } from "react";
import { useSession } from "./useAuthed";

// The authenticated user's real profile (id, full_name, email, phone, role, ...), client-side, via the EXISTING
// /api/account proxy (same one checkout's account prefill and the dashboard forms use) — built on the EXISTING
// useSession() (the same /api/session check Navbar already used), not a second auth check. `user` is null while
// logged out or still loading.
export function useCurrentUser() {
  const { authed, ready } = useSession();
  const [user, setUser] = useState(null);

  useEffect(() => {
    let cancelled = false;
    // Deferred (not called synchronously in the effect body) either way, matching the async fetch branch below.
    if (!ready || !authed) {
      Promise.resolve().then(() => !cancelled && setUser(null));
    } else {
      fetch("/api/account/profile", { cache: "no-store" })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => !cancelled && setUser(data))
        .catch(() => !cancelled && setUser(null));
    }
    return () => {
      cancelled = true;
    };
  }, [ready, authed]);

  return user;
}
