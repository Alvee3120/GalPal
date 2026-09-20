"""
Seed demo catalog data: categories, brands, tags, attributes and products.

    python manage.py seed_catalog            # add demo data (safe to re-run)
    python manage.py seed_catalog --flush     # delete previously-seeded demo data first

Idempotent: every row is looked up by its natural key (slug/sku/name) with `get_or_create`, so
running it again does not create duplicates. Feature images are generated placeholders (solid
colour PNGs) since `Product.feature_image` is required — replace them with real photos whenever
you're ready; nothing else needs to change.
"""

import io
import random
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from PIL import Image, ImageDraw

from apps.catalog import services
from apps.catalog.models import (
    AttributeValue,
    Brand,
    Category,
    Product,
    ProductAttribute,
    ProductImage,
    ProductVariant,
    Tag,
)

# Marks every row this command creates, so `--flush` can remove exactly (and only) those rows.
SEED_TAG = "[seed]"

# 5 top-level + 5 children = 10 categories.
CATEGORIES = [
    ("Skincare", ["Cleansers", "Serums", "Moisturizers", "Sunscreen"]),
    ("Makeup", ["Lips"]),
    ("Hair Care", []),
    ("Body Care", []),
    ("Fragrance", []),
]

BRANDS = ["CeraVe", "The Ordinary", "La Roche-Posay", "Neutrogena", "Innisfree"]

TAGS = ["Vegan", "Cruelty Free", "Fragrance Free", "Paraben Free", "Dermatologist Tested", "Reef Safe", "Sensitive Skin", "Best Value"]

# (name, category path, brand, price, discount, skin_type, is_featured, is_new, is_bestseller, has_variants)
PRODUCTS = [
    ("Hydrating Facial Cleanser", "Skincare/Cleansers", "CeraVe", "850.00", None, ["dry", "normal"], True, False, True, False),
    ("Foaming Facial Cleanser", "Skincare/Cleansers", "CeraVe", "800.00", "650.00", ["oily", "combination"], False, False, False, False),
    ("Salicylic Acid Cleanser", "Skincare/Cleansers", "The Ordinary", "900.00", None, ["oily"], False, True, False, False),
    ("Niacinamide 10% + Zinc 1%", "Skincare/Serums", "The Ordinary", "750.00", None, ["oily", "combination"], True, False, True, False),
    ("Hyaluronic Acid 2% + B5", "Skincare/Serums", "The Ordinary", "780.00", None, ["all"], True, False, True, True),
    ("Vitamin C Suspension 23%", "Skincare/Serums", "The Ordinary", "950.00", "820.00", ["all"], False, True, False, False),
    ("Alpha Arbutin 2% + HA", "Skincare/Serums", "The Ordinary", "820.00", None, ["all"], False, False, False, False),
    ("Moisturizing Cream", "Skincare/Moisturizers", "CeraVe", "1200.00", None, ["dry", "sensitive"], True, False, True, True),
    ("AM Facial Moisturizing Lotion", "Skincare/Moisturizers", "CeraVe", "1100.00", None, ["normal", "combination"], False, False, False, False),
    ("Toleriane Double Repair Moisturizer", "Skincare/Moisturizers", "La Roche-Posay", "1450.00", "1250.00", ["sensitive"], False, False, False, False),
    ("Hydro Boost Water Gel", "Skincare/Moisturizers", "Neutrogena", "1050.00", None, ["oily", "combination"], False, True, False, False),
    ("Anthelios Melt-in Sunscreen SPF50", "Skincare/Sunscreen", "La Roche-Posay", "1600.00", None, ["all"], True, False, True, False),
    ("Ultra Sheer Dry-Touch Sunscreen SPF50", "Skincare/Sunscreen", "Neutrogena", "1400.00", "1200.00", ["all"], False, False, False, False),
    ("Green Tea Seed Serum", "Skincare/Serums", "Innisfree", "1300.00", None, ["oily", "combination"], False, True, False, False),
    ("Matte Lipstick", "Makeup/Lips", None, "600.00", None, [], False, True, False, True),
    ("Tinted Lip Balm", "Makeup/Lips", None, "450.00", "350.00", [], False, False, False, False),
    ("Argan Oil Hair Serum", "Hair Care", None, "700.00", None, [], False, False, False, False),
    ("Anti-Dandruff Shampoo", "Hair Care", None, "550.00", None, [], False, False, True, False),
    ("Shea Butter Body Lotion", "Body Care", None, "650.00", None, ["dry"], False, False, False, False),
    ("Eau de Parfum 50ml", "Fragrance", None, "2200.00", None, [], True, False, False, False),
]

_COLORS = ["#F8BBD0", "#C8E6C9", "#BBDEFB", "#FFE0B2", "#D1C4E9", "#B2EBF2", "#FFF9C4", "#F0F4C3"]


class Command(BaseCommand):
    help = "Seed demo categories, brands, tags, attributes and products (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete previously-seeded demo data first.")

    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()

        with transaction.atomic():
            categories = self._seed_categories()
            brands = self._seed_brands()
            tags = self._seed_tags()
            attribute_values = self._seed_attributes()
            products = self._seed_products(categories, brands, tags)
            self._seed_variants(products, attribute_values)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(categories)} categories, {len(brands)} brands, {len(tags)} tags, "
            f"{Product.objects.filter(sku__startswith='SEED-').count()} products."
        ))
        self.stdout.write("Feature images are solid-colour placeholders — replace them with real photos any time.")

    def _flush(self):
        # hard_delete(), not delete(): Product is soft-delete, and a soft-deleted row would still
        # hold its SKU, colliding with get_or_create() on the next (non-flush) run.
        Product.all_objects.filter(sku__startswith="SEED-").hard_delete()  # cascades to images/variants
        seeded_categories = Category.objects.filter(description__contains=SEED_TAG)
        seeded_categories.filter(parent__isnull=False).delete()  # children first: parent is PROTECT
        seeded_categories.filter(parent__isnull=True).delete()
        Brand.objects.filter(description__contains=SEED_TAG).delete()
        Tag.objects.filter(name__in=TAGS).delete()
        ProductAttribute.objects.filter(name__in=["Shade", "Size"]).delete()
        self.stdout.write("Removed previously-seeded demo data.")

    # --- helpers -----------------------------------------------------------------------------

    def _placeholder_image(self, label):
        color = random.choice(_COLORS)
        image = Image.new("RGB", (600, 600), color)
        draw = ImageDraw.Draw(image)
        draw.text((20, 280), label[:28], fill="#333333")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return ContentFile(buffer.getvalue(), name=f"{label[:20].lower().replace(' ', '-')}.png")

    def _seed_categories(self):
        from apps.core.utils import unique_slugify

        by_path = {}
        for name, children in CATEGORIES:
            slug = unique_slugify(Category, name)
            parent, _ = Category.objects.get_or_create(
                name=name, parent=None, defaults={"slug": slug, "description": f"{SEED_TAG} Demo category."}
            )
            by_path[name] = parent
            for child_name in children:
                child_slug = unique_slugify(Category, child_name)
                child, _ = Category.objects.get_or_create(
                    name=child_name, parent=parent, defaults={"slug": child_slug, "description": f"{SEED_TAG} Demo category."}
                )
                by_path[f"{name}/{child_name}"] = child
        return by_path

    def _seed_brands(self):
        from apps.core.utils import unique_slugify

        brands = {}
        for name in BRANDS:
            slug = unique_slugify(Brand, name)
            brand, _ = Brand.objects.get_or_create(name=name, defaults={"slug": slug, "description": f"{SEED_TAG} Demo brand."})
            brands[name] = brand
        return brands

    def _seed_tags(self):
        from apps.core.utils import unique_slugify

        tags = {}
        for name in TAGS:
            slug = unique_slugify(Tag, name)
            tag, _ = Tag.objects.get_or_create(name=name, defaults={"slug": slug})
            tags[name] = tag
        return tags

    def _seed_attributes(self):
        from apps.core.utils import unique_slugify

        shade, _ = ProductAttribute.objects.get_or_create(name="Shade", defaults={"slug": "shade"})
        size, _ = ProductAttribute.objects.get_or_create(name="Size", defaults={"slug": "size"})
        values = {}
        for attribute, names in [(shade, ["Rose", "Coral", "Nude"]), (size, ["30ml", "50ml", "100ml"])]:
            for name in names:
                slug = unique_slugify(AttributeValue, name)
                value, _ = AttributeValue.objects.get_or_create(
                    attribute=attribute, value=name, defaults={"slug": slug}
                )
                values.setdefault(attribute.name, []).append(value)
        return values

    def _seed_products(self, categories, brands, tags, count=20):
        from apps.core.utils import unique_slugify

        created = []
        tag_pool = list(tags.values())
        for index, spec in enumerate(PRODUCTS[:count], start=1):
            name, path, brand_name, price, discount, skin_type, featured, new, bestseller, has_variants = spec
            sku = f"SEED-{index:03d}"
            product, made = Product.objects.get_or_create(
                sku=sku,
                defaults=dict(
                    name=name,
                    slug=unique_slugify(Product, name),
                    regular_price=Decimal(price),
                    discount_price=Decimal(discount) if discount else None,
                    brand=brands.get(brand_name),
                    skin_type=skin_type,
                    is_featured=featured,
                    is_new_arrival=new,
                    is_bestseller=bestseller,
                    has_variants=has_variants,
                    stock_quantity=0,
                    status="published",
                    short_description=f"{SEED_TAG} {name} — demo product.",
                    feature_image=self._placeholder_image(name),
                ),
            )
            if made:
                services.set_categories(product, [categories[path].id])
                product.tags.set(random.sample(tag_pool, k=min(3, len(tag_pool))))
                services.adjust_stock(
                    product=product, quantity_change=random.randint(10, 100), reason="restock", note=SEED_TAG
                )
                ProductImage.objects.create(product=product, image=self._placeholder_image(f"{name} 2"), sort_order=1)
            created.append(product)
        return created

    def _seed_variants(self, products, attribute_values):
        shades = attribute_values.get("Shade", [])
        if not shades:
            return
        for product in products:
            if not product.has_variants or product.variants.exists():
                continue
            for shade in shades:
                variant = ProductVariant.objects.create(
                    product=product, sku=f"{product.sku}-{shade.slug.upper()}", stock_quantity=0
                )
                services.set_variant_options(variant, [shade.pk])
                services.adjust_stock(variant=variant, product=product, quantity_change=random.randint(5, 30), reason="restock", note=SEED_TAG)
