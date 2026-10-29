# Data only, kept apart from 0003's schema change: PostgreSQL won't build 0003's new index in the same transaction as
# freshly inserted rows whose deferred foreign-key checks are still pending.

from django.db import migrations

# The flag sections, placed where the homepage's hardcoded "Trending Now" sat: after the skincare video, following the
# category sections already there. (source, default title)
FLAG_SECTIONS = [("featured", "Trending Products"), ("new_arrival", "New Arrivals"), ("bestseller", "Bestsellers")]


def seed(apps, schema_editor):
    Section = apps.get_model("content", "HomepageCategorySection")
    if Section.objects.exclude(source="category").exists():
        return
    after = Section.objects.filter(position="after_video").order_by("-sort_order").first()
    order = (after.sort_order + 1) if after else 0
    for source, title in FLAG_SECTIONS:
        Section.objects.create(source=source, title=title, position="after_video", sort_order=order, product_limit=8, rows=1)
        order += 1



class Migration(migrations.Migration):

    dependencies = [
        ("content", "0003_homepage_flag_sections"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
