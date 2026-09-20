import Image from "next/image";

export default function AuthShell({ title, text, children, fit = false }) {
  const main = fit
    ? "auth-page h-[calc(100dvh-4rem)] overflow-hidden px-3 py-3 sm:px-8 sm:py-6 lg:px-12 lg:py-8"
    : "auth-page flex-1 px-4 py-8 sm:px-8 sm:py-12 lg:px-12 lg:py-16";
  const grid = fit
    ? "mx-auto grid h-full min-h-0 w-full max-w-6xl gap-4 lg:grid-cols-2 lg:gap-x-16"
    : "mx-auto grid w-full max-w-6xl gap-8 lg:grid-cols-2 lg:gap-x-16";
  // Nudged toward the left edge of the viewport on desktop.
  const shift = "lg:-translate-x-6 xl:-translate-x-12";
  const left = fit ? `relative hidden min-h-0 flex-col lg:flex ${shift}` : `relative flex flex-col ${shift}`;
  const leftFrame = fit
    ? "auth-frame relative min-h-0 flex-1 lg:mt-24"
    : "auth-frame hidden flex-1 p-2 sm:p-3 md:block lg:mt-24";
  const leftImage = fit
    ? "absolute inset-3"
    : "relative h-64 w-full md:h-72 lg:h-full lg:min-h-[32rem]";
  const right = fit
    ? "auth-frame relative flex h-full min-h-0 flex-col justify-end"
    : "auth-frame relative p-2 sm:p-3";
  const rightImage = fit
    ? "absolute inset-2 sm:inset-3"
    : "relative h-56 w-full sm:h-72 lg:h-full lg:min-h-[40rem]";
  const card = fit
    ? "auth-card relative z-10 mx-4 mb-[clamp(0.5rem,2.5dvh,2rem)] p-[clamp(0.75rem,2.5dvh,2rem)] sm:mx-10 lg:absolute lg:-left-12 lg:bottom-[clamp(0.5rem,4dvh,2.5rem)] lg:mx-0 lg:mb-0 lg:w-[80%]"
    : "auth-card relative -mt-20 mx-3 p-10 sm:mx-10 sm:p-8 lg:absolute lg:-left-12 lg:bottom-10 lg:mx-0 lg:mt-0 lg:w-[80%]";

  return (
    <main className={main}>
      <div className={grid}>
        {/* Left: headline card + photo */}
        <section className={left}>
          <div className="auth-card relative z-10 mx-2 p-6 sm:mx-6 sm:p-8 md:-mb-10 lg:absolute lg:left-10 lg:top-0 lg:mx-0 lg:mb-0 lg:w-[88%]">
            <h1 className="custom-font text-3xl leading-tight sm:text-4xl">{title}</h1>
            <p className="mt-4 text-sm leading-relaxed">{text}</p>
          </div>
          <div className={leftFrame}>
            <div className={leftImage}>
              <Image
                src="/assets/banner/banner1.jpeg"
                alt=""
                fill
                sizes="(min-width: 1024px) 45vw, 90vw"
                className="object-cover object-[70%_center]"
              />
            </div>
          </div>
        </section>

        {/* Right: photo + form card */}
        <section className={right}>
          <div className={rightImage}>
            <Image
              src="/assets/banner/banner2.jpg"
              alt=""
              fill
              priority
              sizes="(min-width: 1024px) 45vw, 90vw"
              className="object-cover object-[center_20%]"
            />
          </div>
          <div className={card}>{children}</div>
        </section>
      </div>
    </main>
  );
}
