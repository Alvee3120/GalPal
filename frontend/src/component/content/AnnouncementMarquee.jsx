"use client";

import { Children, useSyncExternalStore } from "react";
import Marquee from "react-fast-marquee";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

function useReducedMotion() {
  return useSyncExternalStore(
    (onChange) => {
      const query = window.matchMedia(REDUCED_MOTION);
      query.addEventListener("change", onChange);
      return () => query.removeEventListener("change", onChange);
    },
    () => window.matchMedia(REDUCED_MOTION).matches,
    () => false,
  );
}

// Several live announcements scroll by continuously (the same react-fast-marquee the brand strip uses), each followed
// by a small dot, pausing while hovered so a link can be clicked. Visitors who ask for reduced motion get a still row.
export default function AnnouncementMarquee({ children }) {
  const reducedMotion = useReducedMotion();
  const items = Children.toArray(children);
  return (
    <Marquee direction="left" speed={40} pauseOnHover gradient={false} autoFill play={!reducedMotion}>
      {items.map((item, i) => (
        <span key={i} className="inline-flex items-center">
          <span className="mx-6 sm:mx-10">{item}</span>
          <span aria-hidden="true" className="announcement-bar__dot">
            •
          </span>
        </span>
      ))}
    </Marquee>
  );
}
