import pytest

from apps.catalog.tests.factories import ProductFactory
from apps.shipping import seed
from apps.shipping.models import DeliveryMethod, DeliveryZone, District, ShippingChargeHistory, ZoneDistrict
from apps.site_settings.models import SiteSettings


@pytest.fixture(autouse=True)
def shipping_defaults(db):
    """Inside Dhaka 70 / Outside Dhaka 120 (default), the way the seed leaves them. Rebuilt per test, because a
    transactional test elsewhere can flush what the data migration seeded."""
    DeliveryZone.objects.all().delete()
    DeliveryMethod.objects.all().delete()
    ShippingChargeHistory.objects.all().delete()
    seed.seed_all(District, DeliveryZone, ZoneDistrict, DeliveryMethod, ShippingChargeHistory)


@pytest.fixture
def site():
    row, _ = SiteSettings.objects.get_or_create(id=1)
    return row


def set_site(**fields):
    row, _ = SiteSettings.objects.get_or_create(id=1)
    for name, value in fields.items():
        setattr(row, name, value)
    row.save()
    return row


@pytest.fixture
def product(db):
    return ProductFactory(regular_price="500.00", stock_quantity=20, manage_stock=True)
