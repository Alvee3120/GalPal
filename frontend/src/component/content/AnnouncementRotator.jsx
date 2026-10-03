"use client";

import { Children, useEffect, useState } from "react";

const INTERVAL_MS = 5000;

// Shows one announcement at a time, moving to the next every few seconds (paused while hovered or focused).
export default function AnnouncementRotator({ children }) {
  const items = Children.toArray(children);
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (items.length < 2 || paused) return undefined;
    const timer = setInterval(() => setIndex((i) => (i + 1) % items.length), INTERVAL_MS);
    return () => clearInterval(timer);
  }, [items.length, paused]);

  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      aria-live="polite"
    >
      <span key={index % items.length} className="announcement-bar__item inline-block">
        {items[index % items.length]}
      </span>
    </div>
  );
}
