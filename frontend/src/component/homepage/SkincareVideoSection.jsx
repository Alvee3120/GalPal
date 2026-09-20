import Link from "next/link";
import AutoplayVideo from "./AutoplayVideo";
import RevealOnView from "@/component/shared/RevealOnView";

// Videos live in public/video/, so the browser path is /video/<file> (never /public/video/...).
const VIDEOS = [
  { src: "/video/makeup.mp4", eyebrow: "MORNING RITUAL", title: "Barrier Defense" },
  { src: "/video/makeup2.mp4", eyebrow: "EVENING RITUAL", title: "Breathable coverage" },
];

const SHOP_ROUTE = "/shop"; // the shop link used by the navbar, footer and cart

function VideoCard({ video, className = "" }) {
  return (
    <article className={`skv-card group relative aspect-[4/5] overflow-hidden md:aspect-[9/16] ${className}`}>
      <AutoplayVideo src={video.src} className="skv-card__video absolute inset-0 h-full w-full object-cover" />
      <span className="skv-card__shade absolute inset-0" aria-hidden="true" />
      <div className="absolute inset-x-0 bottom-0 p-5 sm:p-6">
        <p className="skv-card__eyebrow text-[0.6875rem] font-medium uppercase tracking-[0.2em]">{video.eyebrow}</p>
        <h3 className="skv-card__title custom-font mt-1.5 text-xl leading-tight sm:text-2xl">{video.title}</h3>
      </div>
    </article>
  );
}

// ONE section, two columns on desktop: editorial text on the left, two portrait videos on the right
// (the second sits lower). On phones it is a single column in the order text -> video 1 -> video 2,
// with shorter (4:5) video cards; from md up they are full portrait 9:16.
export default function SkincareVideoSection() {
  return (
    <section aria-labelledby="skv-heading" className="mx-auto w-full max-w-7xl overflow-x-clip px-4 py-12 sm:px-6 md:py-9 lg:px-8 lg:py-9">
      <div className="grid gap-10 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-center lg:gap-14">
        {/* Text: centered against the whole video composition (the tallest grid row), not against video 1 */}
        <div className="min-w-0">
          <RevealOnView>
            <p className="skv-pill inline-block rounded-full px-4 py-1.5 text-xs font-medium uppercase tracking-[0.25em]">Pure Formulations</p>
            <h2 id="skv-heading" className="skv-heading custom-font mt-6 text-[clamp(2.25rem,4.2vw,4.25rem)] uppercase leading-[0.98]">
              <span className="skv-heading__line block">Your Beauty,</span>
              <span className="skv-heading__accent block italic">Elevated.</span>
            </h2>
          </RevealOnView>

          <RevealOnView delay={100}>
            <p className="skv-text mt-6 max-w-xl text-base leading-relaxed sm:text-lg">
             Discover skincare and makeup crafted to bring out your natural beauty. From daily skin essentials to effortless makeup, find everything you need for your everyday ritual.
            </p>
            <Link href={SHOP_ROUTE} className="skv-cta group mt-8 inline-flex items-center gap-4 rounded-full py-3 pl-8 pr-3 text-sm font-medium uppercase tracking-wider">
              Shop Now
              <span className="skv-cta__arrow flex h-9 w-9 items-center justify-center rounded-full transition-transform duration-300 group-hover:translate-x-1 motion-reduce:transition-none motion-reduce:group-hover:translate-x-0">
                <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M5 12h14M13 6l6 6-6 6" />
                </svg>
              </span>
            </Link>
          </RevealOnView>
        </div>

        {/* Videos: stacked (1 column) on phones, side by side from md; video 2 is staggered lower */}
        <div className="mx-auto grid w-full max-w-[26rem] grid-cols-1 gap-6 md:max-w-2xl md:grid-cols-2 md:items-start md:gap-5 lg:max-w-none">
          <RevealOnView delay={150}>
            <VideoCard video={VIDEOS[0]} />
          </RevealOnView>
          <RevealOnView delay={300} className="md:mt-14 lg:mt-20">
            <VideoCard video={VIDEOS[1]} />
          </RevealOnView>
        </div>
      </div>
    </section>
  );
}
