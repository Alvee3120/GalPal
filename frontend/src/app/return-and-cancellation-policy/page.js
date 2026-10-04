import LegalPage from "@/component/shared/LegalPage";
import CmsPage, { cmsMetadata } from "@/component/content/CmsPage";
import { getContentPage } from "@/lib/content";

const FALLBACK_METADATA = {
  title: "Return & Cancellation Policy | GalPal",
  description: "When a Gal Pal order can be cancelled, which items can be returned or exchanged, and how refunds work.",
};

// Admin → Content Pages can replace this text with a "return-and-cancellation-policy" page; until then the built-in text below shows.
export async function generateMetadata() {
  return cmsMetadata(await getContentPage("return-and-cancellation-policy"), FALLBACK_METADATA);
}

export default async function ReturnCancellationPolicyPage() {
  const page = await getContentPage("return-and-cancellation-policy");
  if (page) return <CmsPage page={page} />;
  return (
    <LegalPage title="Return & Cancellation Policy" intro="Please read the following policy carefully before placing an order." updated="4 October 2026">
      <section>
        <h2>Order Cancellation</h2>
        <ol>
          <li>Orders may be cancelled before they are dispatched, subject to confirmation from our team.</li>
          <li>Once an order has been dispatched, cancellation is no longer possible.</li>
          <li>Once an advance has been paid, cancellation is no longer possible.</li>
          <li>
            For pre-order or specially requested products, cancellation terms may vary and will be communicated to the customer
            at the time of ordering.
          </li>
        </ol>
      </section>

      <section>
        <h2>Returns &amp; Exchanges</h2>
        <p>
          Due to the nature of beauty, skincare, haircare, and cosmetic products, we may only accept returns or exchanges in
          eligible circumstances.
        </p>
        <p>A return or replacement request may be considered if:</p>
        <ol>
          <li>You have received an incorrect product.</li>
          <li>Your order contains a missing item.</li>
          <li>The product arrives damaged or defective.</li>
          <li>The product received does not match the confirmed order.</li>
        </ol>
        <p>Products that have been opened, used, swatched, or otherwise altered are not eligible for return or exchange.</p>
        <p>Change-of-mind returns are not accepted for beauty, skincare, haircare, or cosmetic products.</p>
      </section>

      <section>
        <h2>Damaged or Incorrect Orders</h2>
        <p>
          If your parcel arrives damaged or you receive an incorrect product, please contact us as soon as possible after
          delivery.
        </p>
        <p>
          Customers may be requested to provide clear photographs and/or an unboxing video of the parcel and product so that
          we can assess the issue.
        </p>
        <p>Please keep the original packaging and product until the matter has been resolved.</p>
      </section>

      <section>
        <h2>Refunds</h2>
        <p>If a refund is approved, the applicable refund amount and method will be communicated by our team.</p>
        <p>
          Refund processing time may vary depending on the payment method and financial institution, usually 5-7 business
          days.
        </p>
      </section>

      <section>
        <h2>Return Shipping</h2>
        <p>
          Where a return is approved due to an error on our part, the applicable return delivery arrangement will be
          communicated by Gal Pal.
        </p>
        <p>For other approved returns, return shipping arrangements may vary depending on the circumstances.</p>
      </section>

      <section>
        <h2>Non-Returnable Items</h2>
        <p>
          For hygiene and product-safety reasons, opened or used beauty and personal-care products may not be eligible for
          return or exchange.
        </p>
        <p>Certain sale, promotional, pre-order, or specially requested items may also be subject to specific return conditions.</p>
      </section>

      <section>
        <h2>Important</h2>
        <p>Please contact Gal Pal before sending any product back. Returns sent without prior approval may not be accepted.</p>
        <p>
          Gal Pal reserves the right to assess each return, exchange, replacement, or refund request individually and to
          update this policy when necessary.
        </p>
      </section>
    </LegalPage>
  );
}
