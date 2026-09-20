import Image from "next/image";
import Link from "next/link";

// Editorial 404: a giant "404" whose middle "0" is an arched window holding the GalPal logo.
// Everything is sized in em from one fluid font-size, so the composition scales as a unit and never overflows.
export default function NotFoundPage() {
  return (
    <main
      data-standalone-page
      className="notfound relative isolate flex min-h-[calc(100dvh-4rem)] flex-col items-center justify-center overflow-hidden px-4 py-[clamp(1rem,4dvh,2.5rem)] text-center sm:px-8"
    >
      {/* Soft decorative orbs */}
      <span aria-hidden="true" className="nf-orb pointer-events-none absolute -left-24 top-10 -z-10 h-72 w-72 rounded-full sm:h-96 sm:w-96" />
      <span aria-hidden="true" className="nf-orb pointer-events-none absolute -bottom-24 -right-16 -z-10 h-72 w-72 rounded-full sm:h-[28rem] sm:w-[28rem]" />

      <p className="nf-rise showcase-muted text-xs font-medium uppercase tracking-[0.3em]">Page not found</p>

      <div
        role="img"
        aria-label="Error 404"
        className="nf-rise custom-font mt-[clamp(0.5rem,2dvh,1rem)] flex items-center justify-center text-[clamp(4rem,min(27vw,30dvh),17rem)] leading-none"
        style={{ animationDelay: "80ms", color: "var(--color-brand)" }}
      >
        <span aria-hidden="true">4</span>
        <span aria-hidden="true" className="nf-arch relative mx-[0.03em] inline-block h-[0.86em] w-[0.58em] overflow-hidden rounded-t-full rounded-b-[2.5em]">
          <span className="nf-float absolute inset-[16%] block">
            <Image
              src="/assets/galpal/navlogo.svg"
              alt=""
              fill
              priority
              sizes="(min-width: 1024px) 10rem, 16vw"
              className="object-contain"
            />
          </span>
        </span>
        <span aria-hidden="true">4</span>
      </div>

      <h1 className="nf-rise custom-font mt-[clamp(0.5rem,3dvh,1.5rem)] max-w-xl text-[clamp(1.25rem,min(4.5vw,4.6dvh),2.75rem)] leading-tight" style={{ animationDelay: "160ms" }}>
        This page needs a little
        <br className="[@media(max-height:500px)]:hidden" />
        beauty rest.
      </h1>
      <p className="nf-rise mt-[clamp(0.5rem,2dvh,1rem)] max-w-md text-sm leading-relaxed sm:text-base" style={{ animationDelay: "240ms" }}>
        The page you&apos;re looking for has gone off the shelf. Let&apos;s get you back to your routine.
      </p>

      <div className="nf-rise mt-[clamp(1rem,4dvh,2rem)] flex w-full max-w-sm flex-col gap-3 sm:w-auto sm:max-w-none sm:flex-row" style={{ animationDelay: "320ms" }}>
        <Link href="/" className="auth-btn auth-btn--primary rounded-full px-8 py-[clamp(0.5rem,1.6dvh,0.75rem)] text-sm font-medium transition-transform duration-300 hover:-translate-y-0.5 motion-reduce:transition-none motion-reduce:hover:translate-y-0">
          Back to Home
        </Link>
        <Link href="/shop" className="auth-btn auth-btn--outline rounded-full px-8 py-[clamp(0.5rem,1.6dvh,0.75rem)] text-sm font-medium transition-transform duration-300 hover:-translate-y-0.5 motion-reduce:transition-none motion-reduce:hover:translate-y-0">
          Explore Shop
        </Link>
      </div>
    </main>
  );
}
