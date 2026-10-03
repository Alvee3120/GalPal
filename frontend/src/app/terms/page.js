import Link from "next/link";
import LegalPage from "@/component/shared/LegalPage";
import CmsPage, { cmsMetadata } from "@/component/content/CmsPage";
import { getContentPage } from "@/lib/content";
import { POLICY } from "@/lib/policies";

const FALLBACK_METADATA = {
  title: "Terms of Service | GalPal",
  description: "The terms that apply when you browse, create an account and shop on the GalPal website.",
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
      intro="These terms apply when you use the GalPal website and place an order. By using the site or placing an order, you agree to them."
    >
      <section>
        <h2>Using the Website</h2>
        <ul>
          <li>Please give accurate information when you place an order or create an account.</li>
          <li>Keep your login details private; you&apos;re responsible for activity on your account.</li>
          <li>
            Don&apos;t misuse the website, for example by placing fake orders, interfering with its security or copying
            its content.
          </li>
        </ul>
        <p>We may suspend accounts or cancel orders that break these terms or look fraudulent.</p>
      </section>

      <section>
        <h2>Products &amp; Prices</h2>
        <ul>
          <li>
            We try to show every product, ingredient and price accurately. Colours and packaging may vary slightly from
            the photos.
          </li>
          <li>
            Prices are in Bangladeshi Taka (৳) and can change at any time. The price you pay is the one shown when you
            place your order.
          </li>
          <li>
            If a product was listed with a clear pricing or stock mistake, we&apos;ll contact you and may cancel that item
            or order.
          </li>
          <li>Skincare results vary from person to person. Patch-test new products and follow the directions on the pack.</li>
        </ul>
      </section>

      <section>
        <h2>Orders</h2>
        <ul>
          <li>Your order is an offer to buy; it&apos;s accepted when we confirm it.</li>
          <li>We may contact you by phone to confirm your order before it&apos;s dispatched.</li>
          <li>Products are subject to availability. If something is out of stock after you order, we&apos;ll let you know.</li>
          <li>Coupons must be used as described, can&apos;t be exchanged for cash, and may have conditions such as a minimum order.</li>
        </ul>
      </section>

      <section>
        <h2>Payment</h2>
        <p>
          You can pay with <strong>Cash on Delivery</strong> when you order on the website. Please have the exact amount
          ready for the delivery person. Where online payment is available, a payment counts as received only once it&apos;s
          confirmed.
        </p>
      </section>

      <section>
        <h2>Delivery</h2>
        <ul>
          <li>We deliver across {POLICY.country}. The delivery charge depends on your area and is shown at checkout before you order.</li>
          <li>Delivery times are estimates and may be affected by courier delays, weather, holidays or other events outside our control.</li>
          <li>Please check your parcel when it arrives, and contact us straight away if anything is wrong.</li>
        </ul>
      </section>

      <section>
        <h2>Cancellations, Returns &amp; Refunds</h2>
        <p>
          Cancellations, returns and refunds are covered by our{" "}
          <Link href="/return-and-cancellation-policy">Return &amp; Cancellation Policy</Link>.
        </p>
      </section>

      <section>
        <h2>Reviews</h2>
        <p>
          Reviews must be honest and about your own experience. We moderate reviews before they appear and may decline
          ones that are offensive, misleading or unrelated to the product.
        </p>
      </section>

      <section>
        <h2>Intellectual Property</h2>
        <p>
          The GalPal name, logo, product photos and website content belong to GalPal or its partners. Please don&apos;t
          copy or reuse them without permission.
        </p>
      </section>

      <section>
        <h2>Limitation of Liability</h2>
        <p>
          To the extent allowed by law, GalPal isn&apos;t responsible for indirect losses arising from use of the website
          or products, including reactions from not following product directions. Nothing in these terms limits rights
          you have under the consumer protection laws of {POLICY.country}.
        </p>
      </section>

      <section>
        <h2>Privacy</h2>
        <p>
          How we handle your personal information is explained in our <Link href="/privacy-policy">Privacy Policy</Link>.
        </p>
      </section>

      <section>
        <h2>Changes &amp; Governing Law</h2>
        <p>
          We may update these terms from time to time; the &ldquo;Last updated&rdquo; date above shows the latest version.
          These terms are governed by the laws of {POLICY.country}.
        </p>
      </section>
    </LegalPage>
  );
}
