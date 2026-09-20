"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Image from "next/image";
import TapToPlayVideo from "./TapToPlayVideo";
import ProductSlot from "./ProductSlot";
import SectionHeader from "@/component/shared/SectionHeader";
import CarouselArrows from "@/component/shared/CarouselArrows";

const RESUME_MS = 6000; // autoplay stays paused this long after the user last touched the carousel
const DRAG_THRESHOLD = 5; // px of mouse movement before a press becomes a drag
const PRODUCT_RESUME_MS = 8000; // a video’s product rotation stays paused this long after the visitor touched it

// One horizontal row of shoppable videos, each with ONE fixed product container underneath.
// - Videos never autoplay or loop (see TapToPlayVideo). A video’s products rotate inside its own container every
//   `productRotateMs`; each video rotates independently and rotation never moves the row.
// - The row is a native scroll container (touch swipe, trackpad and wheel just work); only the row scrolls, never the page.
// - When the items do not all fit, the list is rendered three times (clones are aria-hidden/inert) and the scroll
//   position is silently re-centred after each scroll, so it loops endlessly with no gap at either end.
// - It then also advances one item every `autoScrollMs` (0 = off), pausing on hover, focus, touch, drag, wheel, arrow use,
//   while a video is playing, when scrolled off-screen or in a hidden tab, and resuming after RESUME_MS of inactivity.
// - Mouse users can also drag. Reduced-motion users get no autoplay.
export default function VideoProductCarousel({ items, currencySymbol, title, description, autoScrollMs = 4500, productRotateMs = 4000 }) {
  const rootRef = useRef(null);
  const trackRef = useRef(null);
  const [loop, setLoop] = useState(false);
  // which product each video currently shows ({ [videoId]: index }); shared by the real item and its loop clones
  const [shown, setShown] = useState({});
  const rot = useRef({ hover: new Set(), pausedUntil: {} });
  const live = useRef({ hover: false, focus: false, touching: false, dragging: false, visible: true, pausedUntil: 0, idle: 0, drag: null, justDragged: false });

  const measure = useCallback(() => {
    const el = trackRef.current;
    const first = el?.querySelector(":scope > li");
    if (!el || !first) return null;
    const gap = parseFloat(getComputedStyle(el).columnGap) || 0;
    const stride = first.offsetWidth + gap; // distance from one item to the next
    return { stride, setWidth: stride * items.length, overflows: stride * items.length - gap > el.clientWidth + 4 };
  }, [items.length]);

  // Jump without animation (snapping is switched off for the jump so it cannot re-snap mid-way)
  const jumpTo = useCallback((left) => {
    const el = trackRef.current;
    if (!el) return;
    el.style.scrollSnapType = "none";
    el.scrollLeft = left;
    requestAnimationFrame(() => {
      el.style.scrollSnapType = "";
    });
  }, []);

  const pause = useCallback((ms = RESUME_MS) => {
    live.current.pausedUntil = Date.now() + ms;
  }, []);

  // Decide whether the row overflows (=> loop mode), before the first paint and whenever it resizes
  useLayoutEffect(() => {
    const el = trackRef.current;
    if (!el) return;
    const update = () => {
      const m = measure();
      if (m) setLoop(m.overflows);
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, [measure]);

  // Entering/leaving loop mode: start on the middle copy
  useLayoutEffect(() => {
    const m = measure();
    if (m) jumpTo(loop ? m.setWidth : 0);
  }, [loop, measure, jumpTo]);

  // After scrolling settles, hop back to the middle copy (identical content, so the hop is invisible)
  const settle = useCallback(() => {
    const el = trackRef.current;
    const m = measure();
    if (!el || !m || !loop || live.current.dragging || live.current.touching) return;
    if (el.scrollLeft < m.setWidth * 0.5) jumpTo(el.scrollLeft + m.setWidth);
    else if (el.scrollLeft >= m.setWidth * 1.5) jumpTo(el.scrollLeft - m.setWidth);
  }, [loop, measure, jumpTo]);

  const onScroll = () => {
    clearTimeout(live.current.idle);
    live.current.idle = setTimeout(settle, 140);
  };

  const stepBy = useCallback(
    (dir, count = 1) => {
      const el = trackRef.current;
      const m = measure();
      if (el && m) el.scrollBy({ left: dir * m.stride * count, behavior: "smooth" });
    },
    [measure],
  );

  // Arrows move by one group of currently visible items
  const page = (dir) => {
    const el = trackRef.current;
    const m = measure();
    if (!el || !m) return;
    pause();
    stepBy(dir, Math.max(1, Math.floor(el.clientWidth / m.stride)));
  };

  // Autoplay
  useEffect(() => {
    if (!loop || !autoScrollMs || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => {
      const s = live.current;
      if (s.hover || s.focus || s.touching || s.dragging || !s.visible || document.hidden || Date.now() < s.pausedUntil) return;
      if ([...trackRef.current.querySelectorAll("video")].some((v) => !v.paused)) return; // do not slide away from a video being watched
      stepBy(1, 1);
    }, autoScrollMs);
    return () => clearInterval(id);
  }, [loop, autoScrollMs, stepBy]);

  // Product rotation: one timer per video (staggered so they do not all flip at once). It skips a beat while the
  // visitor hovers/focuses/touches that video’s product, or the section is off-screen.
  useEffect(() => {
    if (!productRotateMs) return;
    const cleanups = items.map((item, i) => {
      if (item.products.length < 2) return () => {};
      let interval;
      const start = setTimeout(() => {
        interval = setInterval(() => {
          const s = rot.current;
          if (!live.current.visible || document.hidden || s.hover.has(item.id) || Date.now() < (s.pausedUntil[item.id] ?? 0)) return;
          setShown((cur) => ({ ...cur, [item.id]: ((cur[item.id] ?? 0) + 1) % item.products.length }));
        }, productRotateMs);
      }, (i % 4) * 600);
      return () => {
        clearTimeout(start);
        clearInterval(interval);
      };
    });
    return () => cleanups.forEach((fn) => fn());
  }, [items, productRotateMs]);

  const holdProduct = useCallback((id, ms = PRODUCT_RESUME_MS) => {
    rot.current.pausedUntil[id] = Date.now() + ms;
  }, []);
  const hoverProduct = useCallback(
    (id, on) => {
      if (on) rot.current.hover.add(id);
      else {
        rot.current.hover.delete(id);
        holdProduct(id, 1500);
      }
    },
    [holdProduct],
  );

  // Only run autoplay while the section is on screen
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const observer = new IntersectionObserver(([entry]) => (live.current.visible = entry.isIntersecting), { threshold: 0.2 });
    observer.observe(root);
    return () => observer.disconnect();
  }, []);

  useEffect(() => () => clearTimeout(live.current.idle), []);

  // ----- mouse drag (touch uses the browser's native swipe) -----
  const onPointerDown = (e) => {
    if (e.pointerType !== "mouse" || e.button !== 0 || !loop) return;
    pause();
    live.current.drag = { x: e.clientX, left: trackRef.current.scrollLeft, started: false };
  };
  const onPointerMove = (e) => {
    const s = live.current, el = trackRef.current;
    if (!s.drag || e.pointerType !== "mouse") return;
    const dx = e.clientX - s.drag.x;
    if (!s.drag.started && Math.abs(dx) > DRAG_THRESHOLD) {
      s.drag.started = true;
      s.dragging = true;
      el.dataset.dragging = "true";
      el.setPointerCapture(e.pointerId);
    }
    if (s.drag.started) el.scrollLeft = s.drag.left - dx;
  };
  const endDrag = () => {
    const s = live.current, el = trackRef.current;
    const started = s.drag?.started;
    s.drag = null;
    if (!started) return;
    s.dragging = false;
    s.justDragged = true; // swallow the click that follows a drag
    setTimeout(() => (s.justDragged = false), 0);
    el.dataset.dragging = "false";
    const m = measure();
    if (m) el.scrollTo({ left: Math.round(el.scrollLeft / m.stride) * m.stride, behavior: "smooth" }); // settle on an item
    pause();
  };

  const sets = loop ? 3 : 1;
  const middle = loop ? 1 : 0;

  return (
    <div
      ref={rootRef}
      // Only keyboard focus pauses autoplay; a mouse click leaves a button focused but must not stop it for good
      onFocus={(e) => (live.current.focus = e.target.matches(":focus-visible"))}
      onBlur={() => (live.current.focus = false)}
    >
      <SectionHeader
        title={title}
        description={description}
        actions={loop && <CarouselArrows onPrev={() => page(-1)} onNext={() => page(1)} prevLabel="Previous videos" nextLabel="Next videos" />}
      />

      <ul
        ref={trackRef}
        aria-label={`${title} videos`}
        data-scrollable={loop}
        onScroll={onScroll}
        onPointerEnter={(e) => e.pointerType === "mouse" && (live.current.hover = true)}
        onPointerLeave={(e) => e.pointerType === "mouse" && ((live.current.hover = false), pause(1500))}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onClickCapture={(e) => {
          if (live.current.justDragged) {
            e.preventDefault();
            e.stopPropagation();
          }
        }}
        onWheel={() => pause()}
        onTouchStart={() => ((live.current.touching = true), pause())}
        onTouchEnd={() => ((live.current.touching = false), pause())}
        onTouchCancel={() => (live.current.touching = false)}
        className="vc-track"
      >
        {Array.from({ length: sets }, (_, set) =>
          items.map((item) => {
            const clone = set !== middle;
            return (
              <li key={`${set}-${item.id}`} data-video-id={item.id} className="vc-item" aria-hidden={clone || undefined} inert={clone || undefined}>
                <article>
                  <div className="vc-video relative aspect-[9/16] overflow-hidden">
                    {item.videoUrl ? (
                      <TapToPlayVideo src={item.videoUrl} poster={item.thumbnail} label={`${item.title} video`} className="absolute inset-0 h-full w-full object-cover" />
                    ) : (
                      item.thumbnail && <Image src={item.thumbnail} alt={`${item.title} video`} fill unoptimized draggable={false} sizes="(min-width: 1024px) 24vw, 70vw" className="object-cover" />
                    )}
                  </div>
                  {item.products.length > 0 && (
                    <div className="mt-3">
                      <ProductSlot
                        products={item.products}
                        index={shown[item.id] ?? 0}
                        currencySymbol={currencySymbol}
                        onHover={(on) => hoverProduct(item.id, on)}
                        onInteract={() => holdProduct(item.id)}
                        onSelect={(i) => {
                          holdProduct(item.id);
                          setShown((cur) => ({ ...cur, [item.id]: i }));
                        }}
                      />
                    </div>
                  )}
                </article>
              </li>
            );
          }),
        )}
      </ul>
    </div>
  );
}
