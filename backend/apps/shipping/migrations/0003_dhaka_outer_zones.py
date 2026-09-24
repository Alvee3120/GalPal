"""Add the Dhaka Outer Zones zone (৳100) for Dhamrai, Dohar, Keraniganj, Nawabganj and Savar."""
from django.db import migrations

from apps.shipping import seed


def add_zone(apps, schema_editor):
    seed.seed_dhaka_outer_zone(
        apps.get_model("shipping", "DeliveryZone"),
        apps.get_model("shipping", "ZoneDistrict"),
        apps.get_model("shipping", "District"),
        apps.get_model("shipping", "ShippingChargeHistory"),
    )
    from apps.shipping.services import invalidate_cache

    invalidate_cache()


class Migration(migrations.Migration):
    dependencies = [("shipping", "0002_seed_defaults")]

    # Reversing leaves the zone in place: the Admin may have edited it or orders may reference it.
    operations = [migrations.RunPython(add_zone, migrations.RunPython.noop)]
