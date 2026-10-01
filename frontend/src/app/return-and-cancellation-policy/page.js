import LegalPage from "@/component/shared/LegalPage";
import CmsPage, { cmsMetadata } from "@/component/content/CmsPage";
import { getContentPage } from "@/lib/content";
import { POLICY } from "@/lib/policies";

const FALLBACK_METADATA = {
  title: "Return & Cancellation Policy | GalPal",
  description: "How to cancel a GalPal order, which items can be returned, and how refunds work.",
};

// Admin → Content Pages can replace this text with a "return-and-cancellation-policy" page; until then the built-in text below shows.
export async function generateMetadata() {
  return cmsMetadata(await getContentPage("return-and-cancellation-policy"), FALLBACK_METADATA);
}

export default async function ReturnCancellationPolicyPage() {
  const page = await getContentPage("return-and-cancellation-policy");
  if (page) return <CmsPage page={page} />;
  return (
    <LegalPage
      title="Return & Cancellation Policy"
      intro="We want you to be happy with every order. This policy explains when you can cancel an order, which items can be returned, and how refunds work."
    >
      <section>
        <h2>Cancelling an Order</h2>
        <ul>
          <li>
            <strong>While your order is Pending</strong>, you can cancel it yourself from <em>My Orders</em> in your
            account. Nothing is charged for a cancelled Cash on Delivery order.
          </li>
          <li>
            <strong>Once it&apos;s Confirmed or being prepared</strong>, contact our support team as soon as possible.
            We&apos;ll cancel it if it hasn&apos;t been handed to the courier yet.
          </li>
          <li>
            <strong>After it has shipped</strong>, the order can&apos;t be cancelled. You can refuse the parcel on delivery or
            follow the return steps below.
          </li>
        </ul>
        <p>
          We may cancel an order if a product goes out of stock, the delivery details can&apos;t be confirmed, or the order
          looks fraudulent. If you&apos;ve already paid, you&apos;ll receive a full refund.
        </p>
      </section>

      <section>
        <h2>Returns</h2>
        <p>
          For hygiene and safety, beauty and skincare products can only be returned if they arrive{" "}
          <strong>wrong, damaged, defective or expired</strong>. We&apos;re unable to accept returns for opened or used
          products, or for a change of mind.
        </p>
        <h3>How to request a return</h3>
        <ul>
          <li>
            Contact us within <strong>{POLICY.returnWindowHours} hours of delivery</strong> with your order number.
          </li>
          <li>Share clear photos of the product, its packaging and the parcel label.</li>
          <li>Keep the item unused, in its original packaging, with any free gifts that came with it.</li>
        </ul>
        <p>
          Once we approve the return, we&apos;ll arrange a pickup or tell you how to send it back. If the mistake was ours,
          we cover the return delivery cost.
        </p>
      </section>

      <section>
        <h2>Refunds &amp; Replacements</h2>
        <ul>
          <li>For an approved return, we&apos;ll send a replacement or refund the product&apos;s price, whichever you prefer.</li>
          <li>
            Refunds are issued within <strong>{POLICY.refundWorkingDays} working days</strong> after we receive and check
            the returned item, by mobile banking (e.g. bKash/Nagad) or your original payment method.
          </li>
          <li>Delivery charges are refunded only when the return is because of our mistake.</li>
          <li>Coupon discounts aren&apos;t refundable as cash; the refund is the amount you actually paid.</li>
        </ul>
      </section>

      <section>
        <h2>Refusing a Delivery</h2>
        <p>
          Please check your parcel when it arrives. If it&apos;s clearly damaged, you may refuse it, and let us know so we
          can send a replacement. Repeatedly refusing Cash on Delivery orders without a reason may limit future Cash on
          Delivery orders.
        </p>
      </section>
    </LegalPage>
  );
}
