"use client";

import { useEffect, useRef, useState } from "react";
import { FiPause, FiPlay } from "react-icons/fi";

const PLAY_EVENT = "shoppable-video-play";

// A video that only plays when the visitor asks it to: no autoplay, no loop, no native controls.
// It sits paused on its first frame (or the backend thumbnail); one tap/click/Enter plays it, another pauses it.
// It never restarts by itself: when it ends it returns to the first frame and waits. Only one video plays at a
// time, and a video pauses when it is scrolled out of view. Kept muted (there are no volume controls).
//   poster  backend thumbnail, shown until playback starts
//   lazy    the file is not requested until the video is near the viewport
export default function TapToPlayVideo({ src, poster, label, lazy = true, className = "" }) {
  const ref = useRef(null);
  const wantPlay = useRef(false);
  const [active, setActive] = useState(!lazy);
  const [playing, setPlaying] = useState(false);

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

  // A tap that arrived before the file was assigned starts playback as soon as it is
  useEffect(() => {
    const video = ref.current;
    if (active && wantPlay.current && video) {
      wantPlay.current = false;
      video.play().catch(() => {});
    }
  }, [active]);

  // One video at a time; pause when scrolled out of view
  useEffect(() => {
    const video = ref.current;
    if (!video) return;
    const onOtherPlay = (event) => {
      if (event.detail !== video) video.pause();
    };
    window.addEventListener(PLAY_EVENT, onOtherPlay);
    const observer = new IntersectionObserver(([entry]) => !entry.isIntersecting && video.pause(), { threshold: 0.15 });
    observer.observe(video);
    return () => {
      window.removeEventListener(PLAY_EVENT, onOtherPlay);
      observer.disconnect();
    };
  }, []);

  function toggle() {
    const video = ref.current;
    if (!video) return;
    if (!active) {
      wantPlay.current = true;
      setActive(true);
      return;
    }
    if (video.paused) {
      window.dispatchEvent(new CustomEvent(PLAY_EVENT, { detail: video }));
      video.play().catch(() => {});
    } else {
      video.pause();
    }
  }

  return (
    <>
      <video
        ref={ref}
        src={active ? src : undefined}
        poster={poster || undefined}
        muted
        playsInline
        preload={active ? "metadata" : "none"}
        disablePictureInPicture
        aria-hidden="true"
        tabIndex={-1}
        onPlay={() => {
          window.dispatchEvent(new CustomEvent(PLAY_EVENT, { detail: ref.current }));
          setPlaying(true);
        }}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          // finished: go back to the first frame and wait (never restart on its own)
          if (ref.current) ref.current.currentTime = 0;
          setPlaying(false);
        }}
        className={className}
      />
      <button
        type="button"
        onClick={toggle}
        aria-label={`${playing ? "Pause" : "Play"} ${label}`}
        aria-pressed={playing}
        className="vc-play group/play absolute inset-0 flex items-center justify-center"
      >
        <span className={`vc-play__icon flex h-14 w-14 items-center justify-center rounded-full ${playing ? "vc-play__icon--playing" : ""}`}>
          {playing ? <FiPause className="h-6 w-6" aria-hidden="true" /> : <FiPlay className="ml-0.5 h-6 w-6" aria-hidden="true" />}
        </span>
      </button>
    </>
  );
}
