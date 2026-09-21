import PageHero from "@/component/shared/PageHero";
import CheckoutContent from "@/component/checkout/CheckoutContent";

export const metadata = { title: "Checkout | GalPal" };

export default function CheckoutPage() {
  return (
    <main>
      <PageHero title="Checkout" />
      <div className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <CheckoutContent />
      </div>
    </main>
  );
}
