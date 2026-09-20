from django.db import migrations


def create_default_row(apps, schema_editor):
    HeroSliderConfig = apps.get_model("banners", "HeroSliderConfig")
    HeroSliderConfig.objects.get_or_create(id=1)  # field defaults: 5s delay, autoplay on, loop on


class Migration(migrations.Migration):
    dependencies = [("banners", "0001_initial")]

    operations = [migrations.RunPython(create_default_row, migrations.RunPython.noop)]
