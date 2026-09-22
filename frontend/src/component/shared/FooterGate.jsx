"use client";

import { usePathname } from "next/navigation";

// Routes that render as standalone full-screen pages, without the site footer.
const HIDDEN_ON = ["/login", "/register"];
// Whole sections that never get the public footer — the dashboard has its own full-height shell instead.
const HIDDEN_ON_PREFIX = ["/dashboard"];

export default function FooterGate({ children }) {
  const pathname = usePathname();
  const hidden = HIDDEN_ON.includes(pathname) || HIDDEN_ON_PREFIX.some((prefix) => pathname.startsWith(prefix));
  return hidden ? null : children;
}
