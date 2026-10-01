"""
One command for a realistic demo store (Module 18):

    python manage.py seed_demo            # add whatever is missing (safe to run again)
    python manage.py seed_demo --flush    # remove the demo catalog/reviews/coupons/banners/FAQs first, then re-seed

Runs the per-module seeders — delivery zones (Inside Dhaka ৳70, Outside Dhaka ৳120) and delivery methods, the demo
catalog (categories, brands, tags, products with variants), sample reviews — then adds demo coupons, hero banners
(generated images) and FAQs. Demo rows are marked (SEED- SKUs, DEMO coupon codes, "Demo" banner titles) so --flush
only removes demo data, never real data.
"""

import io
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

DEMO_COUPONS = [
    {"code": "DEMO-WELCOME10", "description": "10% off your first order (up to ৳200), min. ৳500", "type": "percentage",
     "amount": Decimal("10"), "max_discount_amount": Decimal("200"), "min_order_amount": Decimal("500")},
    {"code": "DEMO-FLAT100", "description": "৳100 off orders of ৳1,500 or more", "type": "flat",
     "amount": Decimal("100"), "min_order_amount": Decimal("1500")},
    {"code": "DEMO-EXPIRED", "description": "An expired coupon, to see how checkout rejects it", "type": "flat",
     "amount": Decimal("50"), "expired": True},
]

DEMO_BANNERS = [
    ("Demo – Glow Season", "Glow season: new serums are here", ((107, 1, 39), (214, 120, 150))),
    ("Demo – Bestsellers", "Our bestsellers, loved by thousands", ((40, 40, 60), (120, 90, 160))),
    ("Demo – Sale", "Up to 30% off skincare essentials", ((180, 60, 40), (240, 170, 90))),
]

DEMO_FAQS = [
    ("Orders", "How do I place an order?", "Add products to your cart and go to **Checkout**. Enter your name, phone and address — no account needed."),
    ("Orders", "Can I cancel my order?", "Yes, while it is still pending. Open the order from **My Orders** and choose Cancel, or contact us."),
    ("Delivery", "How much is delivery?", "Inside Dhaka ৳70 and outside Dhaka ৳120. The exact charge for your address is shown at checkout."),
    ("Delivery", "How long does delivery take?", "Usually 1–2 days inside Dhaka and 2–4 days elsewhere in Bangladesh."),
    ("Payment", "Which payment methods do you accept?", "Cash on Delivery for every order. Pay when the parcel arrives."),
    ("Returns", "What if an item arrives damaged?", "Tell us within 48 hours of delivery. See our [Return & Cancellation Policy](/return-and-cancellation-policy)."),
]


def _banner_image(size, colors, text):
    """A simple two-colour gradient JPEG with the banner text, so the demo needs no image files."""
    from PIL import Image, ImageDraw

    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    (r1, g1, b1), (r2, g2, b2) = colors
    for x in range(width):
        t = x / max(width - 1, 1)
        draw.line([(x, 0), (x, height)], fill=(int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t), int(b1 + (b2 - b1) * t)))
    draw.text((width // 12, height // 2), text, fill=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Seed a complete demo store: delivery zones, catalog with variants, reviews, coupons, banners and FAQs."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Remove previously seeded demo data first.")

    def handle(self, *args, flush=False, **options):
        self.stdout.write("Delivery zones & methods…")
        call_command("seed_shipping", stdout=self.stdout)
        self.stdout.write("Catalog…")
        call_command("seed_catalog", flush=flush, stdout=self.stdout)
        self.stdout.write("Reviews…")
        call_command("seed_reviews", flush=flush, stdout=self.stdout)
        if flush:
            call_command("seed_reviews", stdout=self.stdout)  # seed_reviews --flush only deletes
        with transaction.atomic():
            self._coupons(flush)
            self._banners(flush)
            self._faqs(flush)
        self.stdout.write(self.style.SUCCESS("Demo store ready."))

    def _coupons(self, flush):
        from apps.coupons.models import Coupon, CouponUsage

        if flush:
            demo = Coupon.objects.filter(code__startswith="DEMO-")
            CouponUsage.objects.filter(coupon__in=demo).delete()
            demo.delete()
        created = 0
        for spec in DEMO_COUPONS:
            spec = dict(spec)
            expired = spec.pop("expired", False)
            if expired:
                spec["expiry_at"] = timezone.now() - timedelta(days=1)
            _, made = Coupon.objects.get_or_create(code=spec.pop("code"), defaults=spec)
            created += made
        self.stdout.write(f"Coupons: {created} added.")

    def _banners(self, flush):
        from apps.banners.models import HeroBanner
        from apps.banners.services import MAX_BANNERS

        if flush:
            for banner in HeroBanner.objects.filter(title__startswith="Demo"):
                banner.delete()
        room = MAX_BANNERS - HeroBanner.objects.count()
        created = 0
        for order, (title, alt, colors) in enumerate(DEMO_BANNERS[:max(room, 0)]):
            if HeroBanner.objects.filter(title=title).exists():
                continue
            banner = HeroBanner(title=title, alt_text=alt, sort_order=order)  # no link: set your own in the dashboard
            banner.desktop_image.save(f"demo-banner-{order + 1}.jpg", ContentFile(_banner_image((1600, 600), colors, alt)), save=False)
            banner.save()
            created += 1
        self.stdout.write(f"Banners: {created} added (max {MAX_BANNERS} in total).")

    def _faqs(self, flush):
        from apps.content.models import Faq

        if flush:
            Faq.objects.filter(question__in=[q for _, q, _ in DEMO_FAQS]).delete()
        created = 0
        for order, (category, question, answer) in enumerate(DEMO_FAQS):
            _, made = Faq.objects.get_or_create(question=question, defaults={"category": category, "answer": answer, "sort_order": order})
            created += made
        self.stdout.write(f"FAQs: {created} added.")
