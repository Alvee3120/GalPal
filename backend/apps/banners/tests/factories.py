import io

import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.banners.models import HeroBanner, MegaMenuBanner


def make_image(name="banner.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "pink").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue())


class HeroBannerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HeroBanner

    title = factory.Sequence(lambda n: f"Banner {n}")
    desktop_image = factory.LazyFunction(make_image)
    is_active = True
    sort_order = 0


class MegaMenuBannerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MegaMenuBanner

    slot = factory.Iterator(["square_1", "square_2", "wide"])  # a slot may only be used once
    image = factory.LazyFunction(make_image)
    is_active = True
