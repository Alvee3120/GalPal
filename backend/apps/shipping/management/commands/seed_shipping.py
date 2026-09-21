from django.core.management.base import BaseCommand
from django.db import transaction

from apps.shipping import seed, services
from apps.shipping.models import (
    DeliveryMethod,
    DeliveryZone,
    District,
    ShippingChargeHistory,
    ZoneDistrict,
)


class Command(BaseCommand):
    help = (
        "Create the default shipping data if it is missing: the 64 districts, the Inside Dhaka (৳70) and "
        "Outside Dhaka (৳120) zones, and the Standard/Express delivery methods. Safe to run again: "
        "it never overwrites what the Admin has changed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-charges", action="store_true",
            help="Also set the two default zones' charges back to ৳70 / ৳120 (recorded in the charge history).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        result = seed.seed_all(District, DeliveryZone, ZoneDistrict, DeliveryMethod, ShippingChargeHistory)
        self.stdout.write(
            f"Districts created: {result['districts']}. Zones created: {', '.join(result['zones']) or 'none'}. "
            f"Methods created: {', '.join(result['methods']) or 'none'}."
        )
        if options["reset_charges"]:
            for spec in (seed.INSIDE_DHAKA, seed.OUTSIDE_DHAKA):
                zone = DeliveryZone.objects.filter(slug=spec["slug"]).first()
                if zone is None:
                    continue
                if zone.charge != spec["charge"]:
                    services.change_charge(zone, spec["charge"])
                    self.stdout.write(f"Reset {zone.name} to {spec['charge']}.")
        services.invalidate_cache()
