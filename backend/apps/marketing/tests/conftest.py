import pytest

from apps.site_settings.models import SiteSettings


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


@pytest.fixture
def cce_client(auth_client, cce_user):
    return auth_client(cce_user)


def set_site(**fields):
    row, _ = SiteSettings.objects.get_or_create(id=1)
    for name, value in fields.items():
        setattr(row, name, value)
    row.save()
    return row


@pytest.fixture
def meta_configured():
    return set_site(meta_pixel_id="123456789012345", meta_capi_access_token="EAABtest-token-value")


@pytest.fixture
def ga4_configured():
    return set_site(ga4_measurement_id="G-ABCD1234", ga4_api_secret="secret-value")
