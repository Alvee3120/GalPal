from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.banners.models import HeroBanner, HeroSliderConfig

from .factories import HeroBannerFactory, make_image

pytestmark = pytest.mark.django_db


# --- HeroSliderConfig singleton -----------------------------------------------------------


def test_default_row_is_created_by_the_migration():
    row = HeroSliderConfig.objects.get()
    assert row.pk == 1 and row.slide_delay_seconds == 5 and row.autoplay and row.loop


def test_only_one_row_can_ever_exist():
    HeroSliderConfig.objects.create(slide_delay_seconds=9)
    HeroSliderConfig(slide_delay_seconds=3).save()
    assert HeroSliderConfig.objects.count() == 1
    assert HeroSliderConfig.objects.get().slide_delay_seconds == 3


def test_database_rejects_a_second_row():
    with pytest.raises(IntegrityError), transaction.atomic():
        HeroSliderConfig.objects.bulk_create([HeroSliderConfig(id=2)])
    assert HeroSliderConfig.objects.count() == 1


def test_delete_is_refused():
    with pytest.raises(ValidationError):
        HeroSliderConfig.objects.get().delete()
    assert HeroSliderConfig.objects.count() == 1


def test_delay_seconds_range_is_validated():
    row = HeroSliderConfig.objects.get()
    row.slide_delay_seconds = 0
    with pytest.raises(ValidationError):
        row.full_clean()
    row.slide_delay_seconds = 121
    with pytest.raises(ValidationError):
        row.full_clean()


# --- HeroBanner ------------------------------------------------------------------------------


def test_defaults_and_str():
    banner = HeroBannerFactory(title="Summer Sale")
    assert str(banner) == "Summer Sale"
    assert banner.is_active and banner.sort_order == 0 and banner.link_target == "_self"
    assert not banner.tablet_image and not banner.mobile_image and banner.slide_delay_override is None


def test_desktop_image_is_required():
    with pytest.raises(ValidationError):
        HeroBanner(title="X").full_clean()


def test_effective_images_fall_back_to_desktop():
    banner = HeroBannerFactory()
    assert banner.effective_tablet_image == banner.desktop_image
    assert banner.effective_mobile_image == banner.desktop_image


def test_effective_images_use_their_own_when_set():
    tablet, mobile = make_image("t.png"), make_image("m.png")
    banner = HeroBannerFactory(tablet_image=tablet, mobile_image=mobile)
    assert banner.effective_tablet_image.name != banner.desktop_image.name
    assert banner.effective_mobile_image.name != banner.desktop_image.name


def test_end_at_must_be_after_start_at_at_db_level():
    now = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        HeroBannerFactory(start_at=now, end_at=now)
    with pytest.raises(IntegrityError), transaction.atomic():
        HeroBannerFactory(start_at=now, end_at=now - timedelta(days=1))
    HeroBannerFactory(start_at=now, end_at=now + timedelta(days=1))  # fine


def test_link_url_rejects_non_http_schemes():
    banner = HeroBannerFactory(link_url="javascript:alert(1)")
    with pytest.raises(ValidationError):
        banner.full_clean()


def test_ordering_is_sort_order_then_newest_first():
    old = HeroBannerFactory(sort_order=1)
    new = HeroBannerFactory(sort_order=1)
    first = HeroBannerFactory(sort_order=0)
    assert list(HeroBanner.objects.all()) == [first, new, old]
