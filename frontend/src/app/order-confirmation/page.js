import Link from "next/link";
import PageHero from "@/component/shared/PageHero";

export const metadata = { title: "Order Confirmed | GalPal" };

// Where checkout lands after a successful order. "View Invoice" opens /invoice/<number>: the customer's own order
// directly, a guest after confirming the order's phone number.
export default async function OrderConfirmationPage({ searchParams }) {
  const { number } = await searchParams;
  return (
    <main>
      <PageHero title="Order Confirmed" />
      <div className="mx-auto w-full max-w-2xl px-4 pb-16 sm:px-6">
        <div className="shop-empty flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
          <p className="custom-font text-2xl">Thank you for your order!</p>
          {number && <p className="text-sm">Order number: <span className="font-semibold">{number}</span></p>}
          <p className="showcase-muted text-sm">We&apos;ll get it ready for delivery soon.</p>
          <div className="mt-2 flex flex-wrap justify-center gap-3">
            {number && (
              <Link href={`/invoice/${encodeURIComponent(number)}`} className="auth-btn auth-btn--outline rounded-full px-8 py-3 text-sm font-medium">
                View Invoice
              </Link>
            )}
            <Link href="/shop" className="auth-btn auth-btn--primary rounded-full px-8 py-3 text-sm font-medium">
              Continue Shopping
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
