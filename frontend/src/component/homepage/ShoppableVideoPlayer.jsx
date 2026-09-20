"use client";

import { useEffect, useRef, useState } from "react";
import { FiPause, FiPlay, FiVolume1, FiVolume2, FiVolumeX } from "react-icons/fi";

const PLAY_EVENT = "shoppable-video-play";
const RESTORE_VOLUME = 0.5; // used when there is no earlier volume to go back to
const CONTROLS_HIDE_MS = 3500; // touch: how long the controls stay up after a tap

const formatTime = (seconds) => {
  if (!Number.isFinite(seconds)) return "0:00";
  return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
};

// Video with its own premium controls (no native controls): play/pause, seek bar, mute/unmute and a 0-100% volume slider.
// - It never autoplays and never loops. It starts paused with a big play button; sound is available (it is NOT forced
//   muted) and only ever starts after the visitor presses play. At the end it stops on the final frame and shows play again.
// - The video element is the single source of truth: the buttons/sliders write video.play(), pause(), muted, volume and
//   currentTime, and the UI is updated from the element's own events, so it can never drift out of sync.
// - Muting keeps the volume, unmuting restores it (or 50% if it had been 0). Only one video plays at a time, and a video
//   pauses when it is scrolled out of view. It is independent of the product rotation underneath it.
// - Controls show on hover / keyboard focus (desktop) and on tap (touch).
//   poster  backend thumbnail   lazy  the file is not requested until the video is near the viewport
export default function ShoppableVideoPlayer({ src, poster, label, lazy = true, className = "" }) {
  const ref = useRef(null);
  const wantPlay = useRef(false);
  const lastVolume = useRef(1); // the volume to come back to after muting
  const hideTimer = useRef(null);
  const pointerType = useRef("mouse");
  const [active, setActive] = useState(!lazy);
  const [started, setStarted] = useState(false); // has been played at least once
  const [playing, setPlaying] = useState(false);
  const [ended, setEnded] = useState(false);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [time, setTime] = useState({ current: 0, duration: 0 });
  const [revealed, setRevealed] = useState(false); // controls shown by a tap

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

  // A press that arrived before the file was assigned starts playback as soon as it is
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

  useEffect(() => () => clearTimeout(hideTimer.current), []);

  function reveal() {
    setRevealed(true);
    clearTimeout(hideTimer.current);
    hideTimer.current = setTimeout(() => setRevealed(false), CONTROLS_HIDE_MS);
  }

  // ---- actions: write to the video element; state follows from its events ----
  function togglePlay() {
    const video = ref.current;
    if (!video) return;
    if (!active) {
      wantPlay.current = true;
      setActive(true);
      return;
    }
    if (video.paused) video.play().catch(() => {}); // an ended video restarts from 0 when play is pressed
    else video.pause();
  }

  function toggleMute() {
    const video = ref.current;
    if (!video) return;
    if (video.muted || video.volume === 0) {
      video.muted = false;
      if (video.volume === 0) video.volume = lastVolume.current > 0 ? lastVolume.current : RESTORE_VOLUME;
    } else {
      lastVolume.current = video.volume; // remember it, keep the volume itself untouched
      video.muted = true;
    }
  }

  function changeVolume(percent) {
    const video = ref.current;
    if (!video) return;
    const next = Math.min(1, Math.max(0, percent / 100));
    video.volume = next;
    video.muted = next === 0;
    if (next > 0) lastVolume.current = next;
  }

  function seek(permille) {
    const video = ref.current;
    if (video && Number.isFinite(video.duration)) video.currentTime = (permille / 1000) * video.duration;
  }

  const shownVolume = muted ? 0 : Math.round(volume * 100);
  const progress = time.duration ? Math.min(1000, Math.round((time.current / time.duration) * 1000)) : 0;
  const VolumeIcon = muted || volume === 0 ? FiVolumeX : volume < 0.5 ? FiVolume1 : FiVolume2;

  return (
    <div className="absolute inset-0" data-started={started} data-playing={playing}>
      {/* No `muted`, `autoPlay`, `loop` or `controls` attributes: sound is available and the player below is the only UI */}
      <video
        ref={ref}
        src={active ? src : undefined}
        poster={poster || undefined}
        playsInline
        preload={active ? "metadata" : "none"}
        disablePictureInPicture
        aria-hidden="true"
        tabIndex={-1}
        onPlay={() => {
          window.dispatchEvent(new CustomEvent(PLAY_EVENT, { detail: ref.current }));
          setStarted(true);
          setPlaying(true);
          setEnded(false);
        }}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          // stop on the final frame; never restart on its own
          setPlaying(false);
          setEnded(true);
        }}
        onTimeUpdate={(e) => setTime({ current: e.currentTarget.currentTime, duration: e.currentTarget.duration })}
        onLoadedMetadata={(e) => setTime({ current: e.currentTarget.currentTime, duration: e.currentTarget.duration })}
        onVolumeChange={(e) => {
          setVolume(e.currentTarget.volume);
          setMuted(e.currentTarget.muted || e.currentTarget.volume === 0);
        }}
        className={className}
      />

      {/* Click the picture: mouse toggles play/pause, touch shows the controls */}
      <div
        className="absolute inset-0"
        onPointerDown={(e) => (pointerType.current = e.pointerType)}
        onClick={() => (pointerType.current === "mouse" ? togglePlay() : reveal())}
      />

      {!playing && (
        <button
          type="button"
          onClick={togglePlay}
          aria-label="Play video"
          title={label}
          className="vc-play absolute left-1/2 top-1/2 flex h-14 w-14 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full"
        >
          <FiPlay className="ml-0.5 h-6 w-6" aria-hidden="true" />
        </button>
      )}

      {/* Control bar: only after the first play, and only on hover / focus / tap, over a soft gradient */}
      {started && (
        <div
          className="vc-controls absolute inset-x-0 bottom-0 px-3 pb-2.5 pt-8"
          data-revealed={revealed}
          onPointerDown={(e) => {
            e.stopPropagation(); // dragging a slider must not drag the carousel underneath
            if (e.pointerType !== "mouse") reveal();
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <input
            type="range"
            min={0}
            max={1000}
            value={progress}
            onChange={(e) => seek(Number(e.target.value))}
            aria-label="Seek"
            aria-valuetext={`${formatTime(time.current)} of ${formatTime(time.duration)}`}
            className="vc-range block w-full"
            style={{ "--fill": `${progress / 10}%` }}
          />
          <div className="mt-1 flex items-center gap-1">
            <button type="button" onClick={togglePlay} aria-label={playing ? "Pause video" : "Play video"} className="vc-ctl flex h-8 w-8 items-center justify-center rounded-full">
              {playing ? <FiPause className="h-4 w-4" aria-hidden="true" /> : <FiPlay className="ml-0.5 h-4 w-4" aria-hidden="true" />}
            </button>
            <span className="vc-time text-[0.6875rem] tabular-nums">{formatTime(time.current)}</span>
            <span className="flex-1" />
            <button type="button" onClick={toggleMute} aria-label={muted ? "Unmute video" : "Mute video"} className="vc-ctl flex h-8 w-8 items-center justify-center rounded-full">
              <VolumeIcon className="h-4 w-4" aria-hidden="true" />
            </button>
            <input
              type="range"
              min={0}
              max={100}
              value={shownVolume}
              onChange={(e) => changeVolume(Number(e.target.value))}
              aria-label="Volume"
              aria-valuetext={`${shownVolume}%`}
              className="vc-range w-16 shrink-0"
              style={{ "--fill": `${shownVolume}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
