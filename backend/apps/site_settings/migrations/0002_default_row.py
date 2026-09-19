from django.db import migrations


def create_default_row(apps, schema_editor):
    SiteSettings = apps.get_model("site_settings", "SiteSettings")
    SiteSettings.objects.get_or_create(id=1)  # field defaults: GalPal, BDT/৳, guest checkout on, ...


class Migration(migrations.Migration):
    dependencies = [("site_settings", "0001_initial")]

    operations = [migrations.RunPython(create_default_row, migrations.RunPython.noop)]
