"use client";

import { useEffect, useRef, useState } from "react";

// Silent looping video: autoplay + muted + loop + playsInline, no controls, no play button.
// React does not always write the `muted` attribute into server HTML, and browsers only autoplay muted
// videos, so it is set as a property before play() is called. Playback pauses while off-screen (saves CPU/battery).
//   poster  image shown until the first frame is ready (e.g. the backend thumbnail)
//   lazy    do not download the video until it is near the viewport (for rows with many videos)
export default function AutoplayVideo({ src, poster, lazy = false, className }) {
  const ref = useRef(null);
  const [active, setActive] = useState(!lazy);

  // lazy: assign the src only when the video is about to be seen
  useEffect(() => {
    if (!lazy || active) return;
    const video = ref.current;
    if (!video) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setActive(true);
          observer.disconnect();
        }
      },
      { rootMargin: "300px" },
    );
    observer.observe(video);
    return () => observer.disconnect();
  }, [lazy, active]);

  useEffect(() => {
    const video = ref.current;
    if (!video || !active) return;
    video.muted = true;
    video.defaultMuted = true;
    const play = () => video.play().catch(() => {});
    play();

    const observer = new IntersectionObserver(([entry]) => (entry.isIntersecting ? play() : video.pause()), { threshold: 0.15 });
    observer.observe(video);
    return () => observer.disconnect();
  }, [active]);

  return (
    <video
      ref={ref}
      src={active ? src : undefined}
      poster={poster || undefined}
      autoPlay
      muted
      loop
      playsInline
      preload={active ? "metadata" : "none"}
      disablePictureInPicture
      aria-hidden="true"
      tabIndex={-1}
      className={className}
    />
  );
}
