from datetime import timedelta
from unittest import mock

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.banners import services
from apps.banners.models import HeroBanner, HeroSliderConfig

from .factories import HeroBannerFactory

pytestmark = pytest.mark.django_db

NOW = None  # placeholder, set per-test via timezone.now()


# --- cached config reads ----------------------------------------------------------------------


def test_get_slider_config_returns_the_singleton():
    assert services.get_slider_config().pk == 1


def test_second_read_is_served_from_cache(django_assert_num_queries):
    services.get_slider_config()
    with django_assert_num_queries(0):
        services.get_slider_config()


def test_saving_invalidates_the_cache_immediately():
    services.get_slider_config()
    row = HeroSliderConfig.objects.get()
    row.slide_delay_seconds = 12
    row.save()
    assert services.get_slider_config().slide_delay_seconds == 12


def test_reads_fall_back_to_the_database_when_the_cache_is_down(caplog):
    with mock.patch.object(cache, "get", side_effect=ConnectionError("redis down")):
        assert services.get_slider_config().pk == 1
    assert "cache unavailable" in caplog.text


# --- visibility ------------------------------------------------------------------------------


def test_visible_excludes_inactive():
    visible = HeroBannerFactory(is_active=True)
    HeroBannerFactory(is_active=False)
    assert list(services.visible_banners()) == [visible]


def test_visible_respects_the_schedule_window():
    now = timezone.now()
    HeroBannerFactory(start_at=now + timedelta(days=1))  # not yet started
    HeroBannerFactory(end_at=now - timedelta(days=1))  # already ended
    current = HeroBannerFactory(start_at=now - timedelta(days=1), end_at=now + timedelta(days=1))
    no_schedule = HeroBannerFactory()
    assert set(services.visible_banners()) == {current, no_schedule}


def test_visible_only_start_at_set_is_fine():
    now = timezone.now()
    started = HeroBannerFactory(start_at=now - timedelta(hours=1))
    not_started = HeroBannerFactory(start_at=now + timedelta(hours=1))
    assert list(services.visible_banners()) == [started]
    assert not_started


def test_visible_only_end_at_set_is_fine():
    now = timezone.now()
    ongoing = HeroBannerFactory(end_at=now + timedelta(hours=1))
    ended = HeroBannerFactory(end_at=now - timedelta(hours=1))
    assert list(services.visible_banners()) == [ongoing]
    assert ended


def test_visible_ordering_matches_sort_order():
    b = HeroBannerFactory(sort_order=2)
    a = HeroBannerFactory(sort_order=1)
    assert list(services.visible_banners()) == [a, b]


# --- reorder -----------------------------------------------------------------------------------


def test_reorder_sets_sort_order_from_position():
    a, b, c = HeroBannerFactory(), HeroBannerFactory(), HeroBannerFactory()
    services.reorder_banners([c.pk, a.pk, b.pk])
    a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()
    assert (c.sort_order, a.sort_order, b.sort_order) == (0, 1, 2)


def test_reorder_rejects_a_partial_or_extra_list():
    a, b = HeroBannerFactory(), HeroBannerFactory()
    with pytest.raises(ValueError):
        services.reorder_banners([a.pk])
    with pytest.raises(ValueError):
        services.reorder_banners([a.pk, b.pk, 999999])
    a.refresh_from_db(); b.refresh_from_db()
    assert a.sort_order == 0 and b.sort_order == 0  # nothing applied
