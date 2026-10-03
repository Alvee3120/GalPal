import Image from "next/image";
import Link from "next/link";
import { FiArrowRight, FiFileText, FiHeadphones, FiShield, FiStar, FiTruck } from "react-icons/fi";
import PageHero from "@/component/shared/PageHero";
import RichText from "@/component/content/RichText";
import { cmsMetadata } from "@/component/content/CmsPage";
import { getContentPage } from "@/lib/content";
import storyImage from "../../../public/assets/banner/banner1.jpeg";

const FALLBACK_METADATA = {
  title: "About Us | GalPal",
  description: "GalPal brings carefully chosen skincare, makeup and beauty accessories to customers across Bangladesh.",
};

// Category slugs as the homepage uses them (CategoryProductShowcase), linking into the shop's category filter.
const OFFER = [
  { title: "Skincare", text: "Cleansers, serums, moisturisers, sunscreens and treatments for everyday routines.", slug: "skincare" },
  { title: "Makeup", text: "Everyday essentials that complement healthy, glowing skin.", slug: "makeup" },
  { title: "Accessories", text: "Tools and extras that make your routine easier.", slug: "acsosories" },
];

const REASONS = [
  { icon: FiFileText, title: "Clear information", text: "Ingredients, details and prices upfront, with no hidden charges at checkout." },
  { icon: FiShield, title: "Pay on delivery", text: "Cash on Delivery, so you pay only when your order arrives." },
  { icon: FiTruck, title: "Delivery nationwide", text: "We deliver across Bangladesh, with the charge shown before you order." },
  { icon: FiStar, title: "Real reviews", text: "Reviews come from verified purchases and are checked by our team." },
  { icon: FiHeadphones, title: "Friendly support", text: "Help with orders, returns and product questions whenever you need it." },
];

export async function generateMetadata() {
  return cmsMetadata(await getContentPage("about"), FALLBACK_METADATA);
}

// The Our Story text comes from Admin → Content Pages ("about") when that page is active; the rest of the design stays.
export default async function AboutPage() {
  const page = await getContentPage("about");
  return (
    <main>
      <PageHero title="About Us" />
      <div className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        {/* Story: text beside the brand photo (shown whole, never cropped). */}
        <section className="grid items-center gap-10 lg:grid-cols-2 lg:gap-14">
          <div>
            <p className="about-eyebrow text-xs font-semibold uppercase tracking-[0.2em]">Our Story</p>
            {page ? (
              <div className="about-rich about-text mt-3">
                <RichText text={page.content} />
              </div>
            ) : (
              <>
                <h2 className="custom-font mt-3 text-3xl leading-tight sm:text-4xl">Skincare that works, and an honest way to shop for it.</h2>
                <p className="about-text mt-5">
                  We started GalPal because shopping for skincare shouldn&apos;t feel like guesswork. Our focus is
                  high-performance skincare built around barrier repair, gentle and safe formulas, and visible results,
                  alongside makeup and accessories that complete your routine.
                </p>
                <p className="about-text mt-4">
                  Every product in our shop is chosen with care, described clearly and priced upfront, so you know exactly what
                  you&apos;re getting before it reaches your door.
                </p>
              </>
            )}
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/shop" className="auth-btn auth-btn--primary inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-medium">
                Shop Now
                <FiArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link href="/contact" className="auth-btn auth-btn--outline rounded-full px-6 py-3 text-sm font-medium">
                Contact Us
              </Link>
            </div>
          </div>
          <Image
            src={storyImage}
            alt="GalPal model applying cream to her cheek: Unlock your natural glow"
            placeholder="blur"
            sizes="(min-width: 1024px) 50vw, 100vw"
            className="about-photo h-auto w-full rounded-3xl"
            loading="eager"
          />
        </section>

        {/* What we offer: one card per category, linking into the shop. */}
        <section className="mt-20" aria-labelledby="about-offer">
          <div className="text-center">
            <p className="about-eyebrow text-xs font-semibold uppercase tracking-[0.2em]">What We Offer</p>
            <h2 id="about-offer" className="custom-font mt-3 text-3xl sm:text-4xl">
              Everything for your routine
            </h2>
          </div>
          <ul className="mt-10 grid gap-5 md:grid-cols-3">
            {OFFER.map((item) => (
              <li key={item.slug}>
                <Link href={`/shop?category=${item.slug}`} className="about-offer group flex h-full flex-col rounded-2xl p-7">
                  <h3 className="custom-font text-2xl">{item.title}</h3>
                  <p className="about-text mt-3 flex-1 text-sm">{item.text}</p>
                  <span className="about-offer__more mt-6 inline-flex items-center gap-1.5 text-sm font-semibold">
                    Shop {item.title}
                    <FiArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" aria-hidden="true" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        {/* Why shop with us: icon tiles. */}
        <section className="mt-20" aria-labelledby="about-why">
          <div className="text-center">
            <p className="about-eyebrow text-xs font-semibold uppercase tracking-[0.2em]">Why GalPal</p>
            <h2 id="about-why" className="custom-font mt-3 text-3xl sm:text-4xl">
              Why shop with us
            </h2>
          </div>
          <ul className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
            {REASONS.map(({ icon: Icon, title, text }) => (
              <li key={title} className="about-reason flex flex-col items-center rounded-2xl p-6 text-center">
                <span className="about-reason__icon flex h-12 w-12 items-center justify-center rounded-full">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <h3 className="mt-4 font-semibold">{title}</h3>
                <p className="about-text mt-2 text-sm">{text}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* Closing band: confidence + policies. */}
        <section className="about-cta mt-20 rounded-3xl px-6 py-12 text-center sm:px-10" aria-labelledby="about-cta">
          <h2 id="about-cta" className="custom-font text-3xl sm:text-4xl">
            Shop with confidence
          </h2>
          <p className="about-text mx-auto mt-4 max-w-2xl">
            Track your order any time, cancel it while it&apos;s still pending, and reach us if something isn&apos;t right.
            Read our <Link href="/return-and-cancellation-policy">Return &amp; Cancellation Policy</Link>,{" "}
            <Link href="/privacy-policy">Privacy Policy</Link> and <Link href="/terms">Terms of Service</Link>.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <Link href="/shop" className="auth-btn auth-btn--primary rounded-full px-7 py-3 text-sm font-medium">
              Start Shopping
            </Link>
            <Link href="/contact" className="auth-btn auth-btn--outline rounded-full px-7 py-3 text-sm font-medium">
              Get in Touch
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
