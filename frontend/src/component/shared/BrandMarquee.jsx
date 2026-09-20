"use client";

import Image from "next/image";
import Marquee from "react-fast-marquee";

// One group must be wider than the widest viewport, otherwise the track can
// run out of content and expose a gap. 5 items * ~240px already covers most
// screens; repeating up to MIN_ITEMS guarantees it for very wide/short lists.
const MIN_ITEMS = 12;

// Continuously scrolling logo row. `logos` is [{ src, alt }]; `unoptimized` skips
// the Next image optimizer (needed for backends on private hosts).
export default function BrandMarquee({ logos, speed = 40, unoptimized = false }) {
  if (!logos?.length) return null;

  const copies = Math.ceil(MIN_ITEMS / logos.length);
  const items = Array.from({ length: copies }, (_, copy) =>
    logos.map((logo) => ({ ...logo, copy })),
  ).flat();

  return (
    <section aria-label="Brands" className="brand-marquee w-full overflow-hidden py-8 md:py-12">
      <div className="brand-marquee__mask">
        {/* autoFill makes react-fast-marquee repeat the group to fill the container */}
        <Marquee direction="left" speed={speed} pauseOnHover gradient={false} autoFill>
          {/* Spacing is symmetric margin on every item (none on the track ends),
              so the end of one loop meets the start of the next with no gap. */}
          {items.map((logo) => (
            <div
              key={`${logo.copy}-${logo.src}`}
              aria-hidden={logo.copy > 0 ? true : undefined}
              className="brand-marquee__item relative mx-6 h-8 w-24 sm:mx-8 sm:h-10 sm:w-28 md:mx-12 md:h-12 md:w-36"
            >
              <Image
                src={logo.src}
                alt={logo.copy > 0 ? "" : logo.alt}
                fill
                loading="eager"
                unoptimized={unoptimized}
                sizes="(min-width: 768px) 144px, (min-width: 640px) 112px, 96px"
                className="object-contain"
              />
            </div>
          ))}
        </Marquee>
      </div>
    </section>
  );
}
