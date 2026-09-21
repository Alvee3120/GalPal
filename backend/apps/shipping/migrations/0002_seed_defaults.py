"""Seed the 64 districts, the Inside/Outside Dhaka zones (৳70 / ৳120) and the delivery methods."""
from django.db import migrations

from apps.shipping import seed


def seed_defaults(apps, schema_editor):
    seed.seed_all(
        apps.get_model("shipping", "District"),
        apps.get_model("shipping", "DeliveryZone"),
        apps.get_model("shipping", "ZoneDistrict"),
        apps.get_model("shipping", "DeliveryMethod"),
        apps.get_model("shipping", "ShippingChargeHistory"),
    )


class Migration(migrations.Migration):
    dependencies = [("shipping", "0001_initial")]

    # Reversing does nothing on purpose: by then the Admin's own zones may reference these rows,
    # and dropping the tables (0001's reverse) removes them anyway.
    operations = [migrations.RunPython(seed_defaults, migrations.RunPython.noop)]
