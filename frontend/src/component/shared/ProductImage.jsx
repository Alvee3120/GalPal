"use client";

import { useState } from "react";
import Image from "next/image";

// Product photo that degrades to a faint brand mark when the image is missing or fails to load,
// so a broken file never shows a broken-image icon or leaks alt text into the tile.
// `tight` uses minimal padding (thumbnails in compact cards); the default suits the large product tile.
export default function ProductImage({ src, alt, tight = false }) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <Image
        src="/assets/galpal/navlogo.svg"
        alt=""
        fill
        sizes="(min-width: 1024px) 12vw, 24vw"
        className={`object-contain opacity-20 ${tight ? "p-[18%]" : "p-[28%]"}`}
      />
    );
  }

  return (
    <Image
      src={src}
      alt={alt}
      fill
      unoptimized // backend media may live on a private host the Next optimizer cannot reach
      sizes="(min-width: 1024px) 22vw, (min-width: 640px) 30vw, 46vw"
      onError={() => setFailed(true)}
      className={`product-card__img object-contain ${tight ? "p-1" : "p-3 sm:p-5"}`}
    />
  );
}
