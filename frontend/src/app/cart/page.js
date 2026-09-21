import PageHero from "@/component/shared/PageHero";
import CartPageContent from "@/component/cart/CartPageContent";

export const metadata = { title: "Cart | GalPal" };

export default function CartPage() {
  return (
    <main>
      <PageHero title="Cart" />
      <div className="mx-auto w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <CartPageContent />
      </div>
    </main>
  );
}
