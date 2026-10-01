import { getImageProps } from "next/image";
import { getHeroSlider } from "@/lib/heroBanners";
import HeroBannerSlide from "./HeroBannerSlide";
import HeroSwiper from "./HeroSwiper";

// The homepage hero, from Admin → Hero Banners (GET /hero-banners/: only active banners, in the admin's order).
//   1 active banner   -> a plain, static image (Swiper is never loaded)
//   2–3 active banners -> the HeroSwiper slider
//   none, or the API is unreachable -> the site's original static banner, so the homepage never breaks
export default async function Banner() {
  const slider = await getHeroSlider();
  const banners = slider?.banners ?? [];
  if (banners.length === 0) return <StaticFallbackBanner />;
  if (banners.length === 1) {
    return (
      <section aria-label="Featured banner" className="hero-banner">
        <HeroBannerSlide banner={banners[0]} priority />
      </section>
    );
  }
  return <HeroSwiper banners={banners} config={slider.config} />;
}

// Loading state (page.js wraps <Banner/> in Suspense with this): a calm tinted block in the banner's shape.
export function BannerSkeleton() {
  return <div className="hero-banner-skeleton w-full" aria-hidden="true" />;
}

// The original static hero (bundled assets), shown only when no banner has been uploaded/activated or the banner
// API fails. Desktop (banner1) fills the screen height; mobile (banner2) keeps its natural ratio. Both live in one
// <picture>, so only the one matching the viewport is downloaded.
function StaticFallbackBanner() {
  const { props: desktop } = getImageProps({
    src: "/assets/banner/banner1.png",
    width: 1600,
    height: 1000,
    sizes: "100vw",
    quality: 85,
    alt: "",
  });
  const { props: mobile } = getImageProps({
    src: "/assets/banner/banner2.jpg",
    width: 768,
    height: 1376,
    sizes: "100vw",
    quality: 85,
    loading: "eager", // the hero is above the fold (Next 16 replaced `priority`; no preload, so only one image downloads)
    fetchPriority: "high",
    alt: "",
  });

  const { srcSet: desktopSrcSet } = desktop;
  const { srcSet: mobileSrcSet, ...img } = mobile;

  return (
    <section aria-label="Unlock your natural glow" className="w-full">
      <picture>
        <source
          media="(min-width: 768px)"
          srcSet={desktopSrcSet}
          width={1600}
          height={900}
        />
        <source srcSet={mobileSrcSet} width={768} height={1376} />
        <img
          {...img}
          alt="Galopal skincare model applying cream to her cheek: Unlock your natural glow"
          className="block h-auto w-full md:h-screen md:object-cover md:object-center"
        />
      </picture>
    </section>
  );
}
