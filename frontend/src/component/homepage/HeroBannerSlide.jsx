// Plain <img>: backend media may live on a host the Next optimizer cannot reach (same as ProductImage).

// One hero banner filling the hero's fixed full-screen height (globals.css .hero-banner): the image covers it,
// centred, never stretched. The <picture> picks the image for the viewport (desktop / tablet / mobile, each falling
// back to the desktop image in the API), so only one file is downloaded per slide.
export default function HeroBannerSlide({ banner, index = 0, priority = false }) {
  const alt = banner.alt_text || `GalPal banner ${index + 1}`;
  const picture = (
    <picture className="hero-banner__picture">
      <source media="(min-width: 1024px)" srcSet={banner.desktop_image} />
      <source media="(min-width: 768px)" srcSet={banner.tablet_image || banner.desktop_image} />
      <img
        src={banner.mobile_image || banner.desktop_image}
        alt={alt}
        className="hero-banner__img"
        loading="eager"
        decoding="async"
        fetchPriority={priority ? "high" : "auto"}
        draggable={false}
      />
    </picture>
  );

  if (!banner.link_url) return picture;
  return (
    <a
      href={banner.link_url}
      target={banner.link_target || "_self"}
      rel={banner.link_target === "_blank" ? "noopener noreferrer" : undefined}
      className="hero-banner__link"
    >
      {picture}
    </a>
  );
}
