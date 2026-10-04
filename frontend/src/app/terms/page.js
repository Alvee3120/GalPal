import Link from "next/link";
import LegalPage from "@/component/shared/LegalPage";
import CmsPage, { cmsMetadata } from "@/component/content/CmsPage";
import { getContentPage } from "@/lib/content";

const FALLBACK_METADATA = {
  title: "Terms of Service | GalPal",
  description: "The terms that apply when you use the Gal Pal website and place an order: products, orders, pricing, payment, delivery and more.",
};

// Admin → Content Pages can replace this text with a "terms" page; until then the built-in text below shows.
export async function generateMetadata() {
  return cmsMetadata(await getContentPage("terms"), FALLBACK_METADATA);
}

export default async function TermsPage() {
  const page = await getContentPage("terms");
  if (page) return <CmsPage page={page} />;
  return (
    <LegalPage
      title="Terms of Service"
      intro="Welcome to Gal Pal. By accessing or using our website and placing an order through our services, you agree to the following Terms of Service."
      updated="4 October 2026"
      contactTitle="13. Contact Us"
      contactText="If you have questions regarding these Terms of Service, an order, or any of our policies, please contact Gal Pal through the official contact information provided on our website."
    >
      <p>Please read these terms carefully before making a purchase.</p>

      <section>
        <h2>1. Products and Product Information</h2>
        <p>
          We make reasonable efforts to ensure that product names, descriptions, images, availability, and other information
          displayed on our website are accurate.
        </p>
        <p>
          However, colours, packaging, labels, and other visual details may appear slightly different depending on the product
          batch, manufacturer updates, photography, or your device display.
        </p>
        <p>Product availability may change without prior notice.</p>
      </section>

      <section>
        <h2>2. Orders</h2>
        <p>When you place an order through Gal Pal, you are submitting a request to purchase the selected product(s).</p>
        <p>An order is considered confirmed once it has been reviewed and confirmed by Gal Pal.</p>
        <p>We reserve the right to cancel or decline an order in circumstances including, but not limited to:</p>
        <ul>
          <li>Product unavailability</li>
          <li>Incorrect product or pricing information</li>
          <li>Suspected fraudulent activity</li>
          <li>Inability to verify the order</li>
          <li>Other circumstances that prevent us from fulfilling the order</li>
        </ul>
        <p>
          If an order is cancelled after payment has been made, the applicable refund will be handled according to our{" "}
          <Link href="/return-and-cancellation-policy">Return &amp; Cancellation Policy</Link>.
        </p>
      </section>

      <section>
        <h2>3. Pricing</h2>
        <p>All prices displayed on the website are subject to change without prior notice.</p>
        <p>
          We make reasonable efforts to ensure that pricing information is accurate. In the event of an obvious pricing or
          listing error, Gal Pal reserves the right to correct the error and, where necessary, cancel the affected order.
        </p>
        <p>Applicable delivery charges and other fees, if any, will be communicated during the ordering process.</p>
      </section>

      <section>
        <h2>4. Payment</h2>
        <p>Customers are responsible for providing accurate payment and order information.</p>
        <p>Available payment methods may vary and will be displayed or communicated at the time of purchase.</p>
        <p>An order may not be processed until the required payment or confirmation has been received.</p>
      </section>

      <section>
        <h2>5. Delivery</h2>
        <p>Gal Pal delivers orders through third-party courier or delivery services where applicable.</p>
        <p>
          Delivery times are estimates and may vary depending on location, courier operations, weather, public holidays,
          unforeseen circumstances, and other factors beyond our control.
        </p>
        <p>Customers are responsible for providing an accurate and complete delivery address and contact information.</p>
        <p>
          Delays caused by incorrect customer information, failed delivery attempts, or circumstances beyond Gal Pal&apos;s
          reasonable control may not be considered a failure by Gal Pal to fulfil the order.
        </p>
      </section>

      <section>
        <h2>6. Pre-Orders and Special Requests</h2>
        <p>Certain products may be available on a pre-order or special-request basis.</p>
        <p>
          Estimated arrival or delivery timelines for such products may vary. Customers will be informed of relevant conditions
          before confirming their order.
        </p>
        <p>Pre-order and specially requested products may be subject to separate cancellation, return, or refund conditions.</p>
      </section>

      <section>
        <h2>7. Returns, Exchanges and Refunds</h2>
        <p>
          Returns, exchanges, replacements, and refunds are subject to our{" "}
          <Link href="/return-and-cancellation-policy">Return &amp; Cancellation Policy</Link>.
        </p>
        <p>Customers should review that policy before placing an order.</p>
      </section>

      <section>
        <h2>8. Promotions and Discounts</h2>
        <p>Promotional offers, discounts, campaigns, and special offers may be subject to specific terms and conditions.</p>
        <p>Unless otherwise stated, promotional offers cannot be combined with other offers.</p>
        <p>Gal Pal reserves the right to modify or end a promotion according to the terms of the applicable campaign.</p>
      </section>

      <section>
        <h2>9. Website Content</h2>
        <p>
          All text, photographs, graphics, logos, designs, and other content published on the Gal Pal website are owned by or
          used with permission by Gal Pal and/or the respective rights holders.
        </p>
        <p>Website content may not be copied, reproduced, modified, distributed, or used commercially without prior permission.</p>
      </section>

      <section>
        <h2>10. Website Use</h2>
        <p>
          Customers agree not to use the website for unlawful purposes, to interfere with website functionality, attempt
          unauthorized access, or engage in activities that may harm the website, Gal Pal, or other users.
        </p>
      </section>

      <section>
        <h2>11. Third-Party Services</h2>
        <p>
          Gal Pal may use third-party services such as payment gateways, courier services, analytics providers, hosting
          providers, or other technology services.
        </p>
        <p>The availability and operation of such services may be subject to the respective third party&apos;s terms and policies.</p>
      </section>

      <section>
        <h2>12. Changes to These Terms</h2>
        <p>Gal Pal reserves the right to update or modify these Terms of Service from time to time.</p>
        <p>
          The updated version will be published on this page, and continued use of the website after an update may be subject
          to the revised terms.
        </p>
      </section>
    </LegalPage>
  );
}
