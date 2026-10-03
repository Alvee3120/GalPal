"""
Seed demo customers whose carts have been sitting for a while, so Old Carts (Admin + CCE) has something to show.

    python manage.py seed_old_carts           # add the demo carts (safe to re-run)
    python manage.py seed_old_carts --flush   # remove exactly what this command added

Everything is clearly demo data: customer names end in "(Demo)", emails are @demo.galpal.test and the accounts have no
usable password, so nobody can log in as them. Items use real published products (without variants) and are
backdated through the existing `CartItem.created_at`, so ages land in each band (6-24 hours, 1-3 days, 3+ days). One
customer only has an item from 5 hours ago, which correctly does NOT show (old means more than 6 hours). Re-running
rebuilds the same carts instead of adding more.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Product

DEMO_DOMAIN = "demo.galpal.test"

# (full name, phone, [(hours ago, quantity), ...])
DEMO_CARTS = [
    ("Rina Akter (Demo)", "01999000101", [(9, 1), (1, 2)]),  # 9 hours + one added an hour ago (6-24 hours)
    ("Karim Hossain (Demo)", "01999000102", [(120, 1), (118, 2), (100, 1)]),  # ~5 days (3+ days)
    ("Sadia Rahman (Demo)", "01999000103", [(230, 1)]),  # ~9.5 days (3+ days)
    ("Nabila Islam (Demo)", "01999000104", [(30, 1), (3, 1)]),  # 30 hours + 3 hours (1-3 days)
    ("Tanvir Ahmed (Demo)", "01999000105", [(5, 1)]),  # 5 hours: NOT an old cart yet
]


class Command(BaseCommand):
    help = "Add (or --flush) demo customers with old carts for the Old Carts dashboard."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete the demo customers (and their carts).")

    def _demo_users(self):
        return User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["flush"]:
            removed, _ = self._demo_users().delete()  # carts and cart items cascade
            self.stdout.write(self.style.SUCCESS(f"Removed the demo customers and their carts ({removed} rows)."))
            return

        products = list(Product.objects.filter(status="published", has_variants=False).order_by("id")[:12])
        if not products:
            self.stdout.write(self.style.WARNING("No published products without variants: nothing to put in carts."))
            return

        now = timezone.now()
        pick = 0
        for name, phone, lines in DEMO_CARTS:
            email = f"{phone}@{DEMO_DOMAIN}"
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(phone=phone, full_name=name, email=email)
                user.set_unusable_password()
                user.save(update_fields=["password"])
            cart, _ = Cart.objects.get_or_create(user=user, defaults={"token": None})
            cart.items.all().delete()  # rebuild the same demo cart on every run
            for hours_ago, quantity in lines:
                product = products[pick % len(products)]
                pick += 1
                line = CartItem.objects.create(cart=cart, product=product, quantity=quantity)
                CartItem.objects.filter(pk=line.pk).update(created_at=now - timedelta(hours=hours_ago), updated_at=now - timedelta(hours=hours_ago))

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(DEMO_CARTS)} demo customers' carts ({len(DEMO_CARTS) - 1} are old carts; "
            "Tanvir's 5-hour-old item correctly isn't). Remove them with --flush."
        ))
