import pytest

from apps.shipping import seed
from apps.shipping.models import DeliveryMethod, DeliveryZone, District, ZoneDistrict, ShippingChargeHistory


@pytest.fixture(autouse=True)
def clean_shipping(db):
    """
    Every shipping test starts from a known state: the 64 districts, and *no* zones or methods
    (each test builds exactly what it needs, or asks for the `seeded` fixture). The data migration
    seeds the test database once, and a transactional test elsewhere can flush it, so a test must
    never depend on whichever of those happened last.
    """
    DeliveryZone.objects.all().delete()  # cascades to coverage
    DeliveryMethod.objects.all().delete()
    ShippingChargeHistory.objects.all().delete()
    seed.seed_districts(District)


@pytest.fixture
def seeded(db):
    """The default data: Inside Dhaka 70 (Dhaka), Outside Dhaka 120 (default), Standard + Express methods."""
    seed.seed_all(District, DeliveryZone, ZoneDistrict, DeliveryMethod, ShippingChargeHistory)
    return {z.slug: z for z in DeliveryZone.objects.all()}


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)
