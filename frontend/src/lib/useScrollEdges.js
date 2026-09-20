"use client";

import { useCallback, useEffect, useRef, useState } from "react";

// Tracks whether a horizontally scrolling element is at its start/end, and scrolls it by a page.
// Shared by the homepage carousels (category cards, product showcase).
export default function useScrollEdges() {
  const ref = useRef(null);
  const [edges, setEdges] = useState({ start: true, end: true });

  const update = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    setEdges({
      start: el.scrollLeft <= 4,
      end: el.scrollLeft + el.clientWidth >= el.scrollWidth - 4,
    });
  }, []);

  useEffect(() => {
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [update]);

  // dir: -1 (previous) / 1 (next). `fraction` of the visible width; `page` adds the column gap so a
  // full page lands exactly on the next column boundary.
  const scrollBy = useCallback((dir, { fraction = 0.8, page = false } = {}) => {
    const el = ref.current;
    if (!el) return;
    const gap = page ? parseFloat(getComputedStyle(el).columnGap) || 0 : 0;
    el.scrollBy({ left: dir * (el.clientWidth * fraction + gap), behavior: "smooth" });
  }, []);

  return { ref, edges, update, scrollBy };
}
