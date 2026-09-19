import { getImageProps } from "next/image";

// Desktop (banner1): fills the full screen height (100vh) and width. Mobile (banner2): natural ratio, uncropped.
// Both live in one <picture>, so only the one matching the viewport is downloaded.
export default function Banner() {
  const { props: desktop } = getImageProps({
    src: "/assets/banner/banner1.png",
    width: 1600,
    height: 1000,
    sizes: "100vw",
    quality: 85,
    priority: true,
    alt: "",
  });
  const { props: mobile } = getImageProps({
    src: "/assets/banner/banner2.jpg",
    width: 768,
    height: 1376,
    sizes: "100vw",
    quality: 85,
    priority: true,
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
