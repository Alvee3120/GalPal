const arrow = (dir) => (
  <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={dir === "left" ? "M19 12H5M11 6l-6 6 6 6" : "M5 12h14M13 6l6 6-6 6"} />
  </svg>
);

// Previous / next pill buttons, laid out for SectionHeader's grid. Plain flex, no absolute positioning.
export default function CarouselArrows({ onPrev, onNext, prevDisabled = false, nextDisabled = false, prevLabel = "Previous", nextLabel = "Next" }) {
  return (
    <div className="col-start-2 row-start-1 flex shrink-0 items-center gap-2 sm:gap-3 lg:col-auto lg:row-auto">
      <button
        type="button"
        onClick={onPrev}
        disabled={prevDisabled}
        aria-label={prevLabel}
        className="pc-nav flex h-10 w-10 items-center justify-center rounded-full sm:h-12 sm:w-16"
      >
        {arrow("left")}
      </button>
      <button
        type="button"
        onClick={onNext}
        disabled={nextDisabled}
        aria-label={nextLabel}
        className="pc-nav pc-nav--next flex h-10 w-10 items-center justify-center rounded-full sm:h-12 sm:w-16"
      >
        {arrow("right")}
      </button>
    </div>
  );
}
