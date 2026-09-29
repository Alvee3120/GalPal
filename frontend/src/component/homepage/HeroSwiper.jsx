"use client";

import { useState, useSyncExternalStore } from "react";
import { Swiper, SwiperSlide } from "swiper/react";
import { A11y, Autoplay, EffectFade, Keyboard } from "swiper/modules";
import "swiper/css";
import "swiper/css/effect-fade";
import HeroBannerSlide from "./HeroBannerSlide";

const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";
const subscribeMotion = (onChange) => {
  const query = window.matchMedia(REDUCED_MOTION);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
};
const prefersReducedMotion = () => window.matchMedia(REDUCED_MOTION).matches;

// The homepage hero slider for 2–3 active banners (one banner is a plain image — see Banner.jsx — and never mounts
// Swiper). Smooth horizontal slide: 800ms ease, autoplay (the admin's slider config; a banner's own delay override
// wins), loop, touch + mouse drag with resistance, keyboard arrows, and dot buttons. Every slide is one full screen
// high (globals.css .hero-banner). With prefers-reduced-motion: no autoplay and no slide animation — the dots still
// switch banners.
export default function HeroSwiper({ banners, config }) {
  const reducedMotion = useSyncExternalStore(subscribeMotion, prefersReducedMotion, () => false);
  const [swiper, setSwiper] = useState(null);
  const [active, setActive] = useState(0);

  // Smoothness: 0.7s cross-fades on a gentle ease-in-out curve (globals.css), GPU-composited, images decoded off
  // the main thread before they appear. Swiper's loop needs more slides than are visible at once to never show a
  // blank edge; two banners are rendered twice (A B A B), the dots still count the real banners.
  const slides = banners.length === 2 ? [...banners, ...banners] : banners;
  const delay = Math.max(1, Number(config?.slide_delay_seconds) || 5) * 1000;
  const SPEED = 700;
  const loop = config?.loop !== false;
  const autoplay = config?.autoplay !== false && !reducedMotion;
  // "Grow and change": each banner slowly zooms in for as long as it's shown (its delay + the fade out), then the
  // next one fades in and grows in turn (globals.css .hero-banner__swiper--grow). Off with reduced motion or no autoplay.
  const grow = autoplay;
  const growMs = (seconds) => `${(seconds ? seconds * 1000 : delay) + SPEED}ms`;

  return (
    <section aria-roledescription="carousel" aria-label="Featured banners" className="hero-banner">
      <Swiper
        modules={[Autoplay, Keyboard, A11y, EffectFade]}
        slidesPerView={1}
        // No sliding: the next banner cross-fades in over the current one (which keeps growing while it fades out).
        // A swipe or drag still changes banner, with the same fade.
        effect="fade"
        fadeEffect={{ crossFade: true }}
        loop={loop}
        speed={reducedMotion ? 0 : SPEED}
        grabCursor
        // Dragging: follows the finger 1:1, a light flick or a quarter-width drag changes slide, soft edge resistance,
        // and a small threshold so a tap or vertical scroll never nudges the slider.
        threshold={6}
        longSwipesRatio={0.25}
        resistance
        resistanceRatio={0.85}
        touchStartPreventDefault={false}
        keyboard={{ enabled: true, onlyInViewport: true }}
        autoplay={autoplay ? { delay, disableOnInteraction: false, pauseOnMouseEnter: true, waitForTransition: true } : false}
        a11y={{ enabled: true, prevSlideMessage: "Previous banner", nextSlideMessage: "Next banner" }}
        onSwiper={setSwiper}
        // Dots update once a slide has settled, so React never re-renders mid-slide.
        onSlideChangeTransitionEnd={(s) => setActive(s.realIndex % banners.length)}
        className={`hero-banner__swiper${grow ? " hero-banner__swiper--grow" : ""}`}
      >
        {slides.map((banner, i) => (
          <SwiperSlide
            key={`${banner.id}-${i}`}
            data-swiper-autoplay={banner.slide_delay_override ? banner.slide_delay_override * 1000 : undefined}
            style={grow ? { "--hero-grow-duration": growMs(banner.slide_delay_override) } : undefined}
          >
            <HeroBannerSlide banner={banner} index={i % banners.length} priority={i === 0} />
          </SwiperSlide>
        ))}
      </Swiper>

      <div className="hero-banner__dots" role="group" aria-label="Choose banner">
        {banners.map((banner, i) => (
          <button
            key={banner.id}
            type="button"
            className="hero-banner__dot"
            aria-label={`Show banner ${i + 1} of ${banners.length}`}
            aria-current={i === active ? "true" : undefined}
            onClick={() => (loop ? swiper?.slideToLoop(i) : swiper?.slideTo(i))}
          />
        ))}
      </div>
    </section>
  );
}
