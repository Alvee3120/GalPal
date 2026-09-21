import factory

from apps.shipping.models import DeliveryMethod, DeliveryZone, District, ZoneDistrict


class DeliveryZoneFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeliveryZone
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Zone {n}")
    slug = factory.Sequence(lambda n: f"zone-{n}")
    charge = "100.00"
    is_active = True

    @factory.post_generation
    def _reload(obj, create, extracted, **kwargs):
        # Money handed in as a str would stay a str on the instance; reload so it holds what the
        # database returns (Decimal), exactly as production code sees it.
        if create:
            obj.refresh_from_db()


class DeliveryMethodFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeliveryMethod
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Method {n}")
    slug = factory.Sequence(lambda n: f"method-{n}")
    extra_charge = "50.00"
    is_active = True

    @factory.post_generation
    def _reload(obj, create, extracted, **kwargs):
        if create:
            obj.refresh_from_db()


def district(name):
    return District.objects.get(name=name)


def cover(zone, *names, areas=None):
    """Make `zone` cover the named districts (whole, or only `areas` of each)."""
    for name in names:
        ZoneDistrict.objects.create(zone=zone, district=district(name), areas=list(areas or []))
    return zone
