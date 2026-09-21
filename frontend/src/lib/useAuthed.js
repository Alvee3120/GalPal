"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

// Session state from the project's existing /api/session route (reads the refresh_token cookie server-side — see
// app/api/session/route.js). This is the SAME check Navbar.jsx runs for the account icon; extracted so other
// features reuse it instead of adding a second auth check. Re-checked on every navigation, so it updates right
// after login/logout. `ready` is false until the first answer arrives (so callers can avoid flashing guest UI).
export function useSession() {
  const pathname = usePathname();
  const [state, setState] = useState({ authed: false, ready: false });

  useEffect(() => {
    let cancelled = false;
    fetch("/api/session", { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => !cancelled && setState({ authed: Boolean(data.authenticated), ready: true }))
      .catch(() => !cancelled && setState({ authed: false, ready: true }));
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  return state;
}

export function useAuthed() {
  return useSession().authed;
}
