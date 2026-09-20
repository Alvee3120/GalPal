"use client";

import { useEffect, useRef } from "react";

// The oversized "Galpal" wordmark: cropped to its top part and fading out (decorative). When it scrolls into
// view the lettering rises up from below its crop line; leaving the view re-arms it so it rises again next time.
// Server HTML is fully visible (no-JS safe); hiding only starts after hydration. Styles: .footer-wordmark in globals.css.
export default function FooterWordmark() {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.dataset.wordmark = "pending";
    void el.offsetHeight; // commit the hidden state so the first reveal animates even if already in view
    const observer = new IntersectionObserver(
      ([entry]) => {
        el.dataset.wordmark = entry.isIntersecting ? "shown" : "pending";
      },
      { threshold: 0.25 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      aria-hidden="true"
      className="footer-wordmark custom-font pointer-events-none mt-8 h-[0.65em] select-none overflow-hidden whitespace-nowrap text-center text-[24vw] leading-[1.2]"
    >
      <span className="footer-wordmark__text inline-block">Galpal</span>
    </div>
  );
}
