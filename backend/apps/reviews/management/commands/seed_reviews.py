"""
Seed sample approved reviews so the storefront's review sections (product pages, homepage testimonials) have
content to show.

    python manage.py seed_reviews             # add sample reviews (safe to re-run)
    python manage.py seed_reviews --flush     # remove exactly the reviews this command added

They go through the existing manual/testimonial path (`services.create_manual_review`: `is_manual=True`, no customer
account), so they are clearly marked as staff-entered in Review Management, are never "Verified purchase", and the
product ratings are recomputed by the usual review signal. Re-running adds nothing new: each sample is looked up by
product + reviewer + text first.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Product
from apps.reviews import services
from apps.reviews.models import Review, ReviewStatus

# (reviewer, rating, title, text)
SAMPLES = [
    ("Nusrat J.", 5, "My skin loves it", "Light, absorbs quickly and leaves no sticky feel. After two weeks my skin looks noticeably brighter."),
    ("Farzana A.", 5, "Worth every taka", "Genuine product, well packed and delivered in two days. I've already ordered a second one for my sister."),
    ("Sadia R.", 4, "Great for daily use", "Gentle enough for every day. The scent is subtle and it layers nicely under makeup."),
    ("Tahmina K.", 5, "Holy grail", "I've tried so many before this and nothing comes close. Hydrating without being heavy in our humidity."),
    ("Rafiq H.", 4, "Bought it for my wife", "She uses it every night and says it's the best she's had. Fast delivery and helpful customer care."),
    ("Mehjabin S.", 5, "Glow is real", "Makeup sits so much better now. A little goes a long way, so one bottle lasts ages."),
    ("Ayesha B.", 4, "Very good", "Nice texture and no breakouts on my sensitive skin. Would love a bigger size option."),
    ("Sumaiya T.", 5, "Beautiful packaging", "Looks and feels premium. Arrived sealed and exactly as pictured. Highly recommend GalPal."),
    ("Nabila I.", 5, "Repurchasing", "Third bottle already. My dark spots have faded and my skin feels so soft."),
    ("Tanvir A.", 4, "Good value", "Works well and the price is fair for an original product. Customer care confirmed my order by phone right away."),
    ("Rumana P.", 5, "Obsessed", "Smells lovely, feels luxurious and actually works. My new favourite part of my routine."),
    ("Ishrat Z.", 5, "Perfect gift", "Bought it as a gift and ended up keeping one for myself. Everyone asks what I've been using."),
]


class Command(BaseCommand):
    help = "Add (or --flush) sample approved reviews for published products."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete the sample reviews this command created.")

    def _seeded(self):
        texts = [text for *_, text in SAMPLES]
        return Review.objects.filter(is_manual=True, created_by__isnull=True, text__in=texts)

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            removed = 0
            for review in self._seeded():
                services.delete_review(review)  # also removes images; the signal recomputes the rating
                removed += 1
            self.stdout.write(self.style.SUCCESS(f"Removed {removed} sample review(s)."))
            return

        products = list(Product.objects.filter(status="published").order_by("id")[: len(SAMPLES)])
        if not products:
            self.stdout.write(self.style.WARNING("No published products: nothing to review."))
            return

        created = 0
        for index, (name, rating, title, text) in enumerate(SAMPLES):
            product = products[index % len(products)]  # spread across products, round-robin
            if Review.objects.filter(product=product, reviewer_name=name, text=text).exists():
                continue
            services.create_manual_review(
                product=product, reviewer_name=name, rating=rating, title=title, text=text,
                status=ReviewStatus.APPROVED, created_by=None,
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Created {created} sample review(s) across {len(products)} product(s)."))
