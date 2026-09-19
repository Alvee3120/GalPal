import io
from unittest import mock

import pytest
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.tests.factories import AdminFactory
from apps.site_settings import services
from apps.site_settings.models import SiteSettings

pytestmark = pytest.mark.django_db


def image(name="logo.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "pink").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue())


# --- cached reads -----------------------------------------------------------------------------


def test_get_site_settings_returns_the_singleton():
    row = services.get_site_settings()
    assert isinstance(row, SiteSettings) and row.pk == 1


def test_second_read_is_served_from_cache_with_zero_queries(django_assert_num_queries):
    services.get_site_settings()
    with django_assert_num_queries(0):
        assert services.get_site_settings().site_name == "GalPal"


def test_first_read_hits_the_database_once(django_assert_num_queries):
    with django_assert_num_queries(1):
        services.get_site_settings()


def test_saving_invalidates_the_cache_immediately():
    services.get_site_settings()
    row = SiteSettings.objects.get()
    row.site_name = "Renamed"
    row.save()
    assert services.get_site_settings().site_name == "Renamed"


def test_invalidation_also_runs_after_commit(django_capture_on_commit_callbacks):
    services.get_site_settings()
    with django_capture_on_commit_callbacks(execute=True):
        row = SiteSettings.objects.get()
        row.tagline = "New"
        row.save()
        # simulate a concurrent request re-caching the old data before the commit lands
        cache.set(services.CACHE_KEY, SiteSettings(site_name="STALE"), 60)
    assert services.get_site_settings().site_name != "STALE"


def test_missing_row_is_recreated_with_defaults():
    SiteSettings.objects.all().delete()  # queryset delete bypasses the model guard
    cache.clear()
    row = services.get_site_settings()
    assert row.site_name == "GalPal" and SiteSettings.objects.count() == 1


def test_cache_ttl_comes_from_settings(settings):
    settings.SITE_SETTINGS_CACHE_TTL = 123
    with mock.patch("apps.site_settings.services.cache") as fake_cache:
        fake_cache.get.return_value = None
        services.get_site_settings()
    assert fake_cache.set.call_args.args[2] == 123


# --- cache outage: degrade, never fail ----------------------------------------------------------


def test_reads_fall_back_to_the_database_when_the_cache_is_down(caplog):
    with mock.patch.object(cache, "get", side_effect=ConnectionError("redis down")), \
         mock.patch.object(cache, "set", side_effect=ConnectionError("redis down")):
        assert services.get_site_settings().site_name == "GalPal"
    assert "cache unavailable" in caplog.text


def test_saves_survive_a_cache_that_cannot_be_invalidated():
    with mock.patch.object(cache, "delete", side_effect=ConnectionError("redis down")):
        row = SiteSettings.objects.get()
        row.tagline = "still saved"
        row.save()
    assert SiteSettings.objects.get().tagline == "still saved"


def test_a_real_unreachable_redis_does_not_break_reads_or_writes(settings):
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": "redis://127.0.0.1:6390/0",  # nothing listens here
            "OPTIONS": {"socket_connect_timeout": 1, "socket_timeout": 1},
        }
    }
    assert services.get_site_settings().site_name == "GalPal"
    row = SiteSettings.objects.get()
    row.tagline = "written while redis is down"
    row.save()
    assert services.get_site_settings().tagline == "written while redis is down"


# --- update_site_settings -----------------------------------------------------------------------


def test_update_sets_fields_and_records_who_changed_it():
    admin = AdminFactory()
    row = services.update_site_settings(SiteSettings.objects.get(), user=admin, site_name="X", tax_percent="5.00")
    row.refresh_from_db()
    assert row.site_name == "X" and str(row.tax_percent) == "5.00" and row.updated_by == admin


def test_replacing_an_image_removes_the_old_file_after_commit(django_capture_on_commit_callbacks):
    row = SiteSettings.objects.get()
    with django_capture_on_commit_callbacks(execute=True):
        services.update_site_settings(row, logo=image("one.png"))
    first = SiteSettings.objects.get().logo.name
    assert default_storage.exists(first) and first.startswith("branding/")

    with django_capture_on_commit_callbacks(execute=True):
        services.update_site_settings(SiteSettings.objects.get(), logo=image("two.png"))
    second = SiteSettings.objects.get().logo.name
    assert second != first and default_storage.exists(second) and not default_storage.exists(first)


def test_clearing_an_image_removes_the_file(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        services.update_site_settings(SiteSettings.objects.get(), favicon=image())
    name = SiteSettings.objects.get().favicon.name
    with django_capture_on_commit_callbacks(execute=True):
        services.update_site_settings(SiteSettings.objects.get(), favicon=None)
    assert not SiteSettings.objects.get().favicon and not default_storage.exists(name)


def test_untouched_image_is_kept(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        services.update_site_settings(SiteSettings.objects.get(), logo=image())
    name = SiteSettings.objects.get().logo.name
    with django_capture_on_commit_callbacks(execute=True):
        services.update_site_settings(SiteSettings.objects.get(), site_name="Other")
    assert default_storage.exists(name)


def test_old_file_is_kept_if_the_transaction_rolls_back(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        services.update_site_settings(SiteSettings.objects.get(), logo=image())
    name = SiteSettings.objects.get().logo.name
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(RuntimeError):
            with mock.patch.object(SiteSettings, "save", side_effect=RuntimeError("boom")):
                services.update_site_settings(SiteSettings.objects.get(), logo=image("new.png"))
    assert callbacks == [] and default_storage.exists(name)
