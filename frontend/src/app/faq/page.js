import Link from "next/link";
import PageHero from "@/component/shared/PageHero";
import RichText from "@/component/content/RichText";
import { getFaqs } from "@/lib/content";

export const metadata = {
  title: "FAQ | GalPal",
  description: "Answers to common questions about ordering, delivery, payment and returns at GalPal.",
};

// Frequently asked questions (Admin → FAQs), grouped by category in the order the Admin set. Native <details> so it
// works without JavaScript.
export default async function FaqPage() {
  const faqs = await getFaqs();
  const groups = [];
  for (const faq of faqs) {
    const name = faq.category || "General";
    let group = groups.find((g) => g.name === name);
    if (!group) groups.push((group = { name, items: [] }));
    group.items.push(faq);
  }

  return (
    <main>
      <PageHero title="Frequently Asked Questions" />
      <div className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        {groups.length === 0 ? (
          <p className="showcase-muted text-center">
            No questions here yet. <Link href="/contact" className="underline">Contact us</Link> and we&apos;ll be happy to help.
          </p>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-10">
            {groups.map((group) => (
              <section key={group.name} aria-label={group.name}>
                {groups.length > 1 && <h2 className="custom-font text-2xl font-bold">{group.name}</h2>}
                <div className="mt-4 flex flex-col gap-3">
                  {group.items.map((faq) => (
                    <details key={faq.id} className="faq-item dashboard-card rounded-2xl px-5 py-4">
                      <summary className="cursor-pointer font-semibold">{faq.question}</summary>
                      <div className="faq-item__answer legal-page mt-3 text-sm">
                        <RichText text={faq.answer} />
                      </div>
                    </details>
                  ))}
                </div>
              </section>
            ))}
            <p className="showcase-muted text-center text-sm">
              Still have a question? <Link href="/contact" className="underline">Get in touch</Link>.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
