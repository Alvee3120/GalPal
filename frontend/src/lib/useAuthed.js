"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

// Whether a session exists, via the project's existing /api/session route (reads the refresh_token
// cookie server-side — see app/api/session/route.js). This is the SAME check Navbar.jsx already
// runs for the account icon; extracted here so Notify Me can reuse it instead of adding a second
// auth check. Re-checked on every navigation, so it updates right after login/logout.
export function useAuthed() {
  const pathname = usePathname();
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/session", { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => !cancelled && setAuthed(Boolean(data.authenticated)))
      .catch(() => !cancelled && setAuthed(false));
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  return authed;
}
