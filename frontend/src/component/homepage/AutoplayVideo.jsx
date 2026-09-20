"use client";

import { useEffect, useRef } from "react";

// Silent looping background video: autoplay + muted + loop + playsInline, no controls, no play button.
// React does not always write the `muted` attribute into server HTML, and browsers only autoplay muted
// videos, so it is set as a property before play() is called. Playback pauses while off-screen (saves CPU/battery).
export default function AutoplayVideo({ src, className }) {
  const ref = useRef(null);

  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    video.muted = true;
    video.defaultMuted = true;
    const play = () => video.play().catch(() => {});
    play();

    const observer = new IntersectionObserver(([entry]) => (entry.isIntersecting ? play() : video.pause()), { threshold: 0.15 });
    observer.observe(video);
    return () => observer.disconnect();
  }, []);

  return (
    <video
      ref={ref}
      src={src}
      autoPlay
      muted
      loop
      playsInline
      preload="metadata"
      disablePictureInPicture
      aria-hidden="true"
      tabIndex={-1}
      className={className}
    />
  );
}
