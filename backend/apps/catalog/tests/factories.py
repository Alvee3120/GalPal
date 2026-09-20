import io

import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from slugify import slugify

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


def make_image(name="p.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "pink").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue())


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    parent = None
    is_active = True
    sort_order = 0


class BrandFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Brand

    name = factory.Sequence(lambda n: f"Brand {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    is_active = True


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"Tag {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Product {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))
    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    feature_image = factory.LazyFunction(make_image)
    regular_price = "1000.00"
    status = "published"


class ProductImageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductImage

    product = factory.SubFactory(ProductFactory)
    image = factory.LazyFunction(make_image)
    sort_order = 0


class ProductAttributeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductAttribute

    name = factory.Sequence(lambda n: f"Attribute {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))


class AttributeValueFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AttributeValue

    attribute = factory.SubFactory(ProductAttributeFactory)
    value = factory.Sequence(lambda n: f"Value {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.value))


class ProductVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ProductVariant
        skip_postgeneration_save = True

    product = factory.SubFactory(ProductFactory)
    sku = factory.Sequence(lambda n: f"VAR-{n:05d}")

    @factory.post_generation
    def attribute_values(self, create, extracted, **kwargs):
        if create and extracted:
            from apps.catalog import services

            services.set_variant_options(self, [v.pk for v in extracted])
