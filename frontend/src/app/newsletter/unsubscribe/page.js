import PageHero from "@/component/shared/PageHero";
import UnsubscribeConfirm from "@/component/content/UnsubscribeConfirm";

export const metadata = { title: "Unsubscribe | GalPal", robots: { index: false } };

// The link in every newsletter: /newsletter/unsubscribe?token=… — the visitor confirms with a button (so link
// previews and mail scanners that open links can't unsubscribe anyone).
export default async function UnsubscribePage({ searchParams }) {
  const { token } = await searchParams;
  return (
    <main>
      <PageHero title="Newsletter" />
      <div className="mx-auto w-full max-w-xl px-4 pb-16 text-center sm:px-6">
        <UnsubscribeConfirm token={typeof token === "string" ? token : ""} />
      </div>
    </main>
  );
}
