from datetime import timedelta

import pytest
from django.utils import timezone

from apps.banners.models import HeroSliderConfig

from .factories import HeroBannerFactory, make_image

pytestmark = pytest.mark.django_db

SLIDER = "/api/v1/hero-banners/"


def test_shape_has_config_and_banners(api_client):
    body = api_client.get(SLIDER).json()
    assert set(body) == {"config", "banners"}
    assert set(body["config"]) == {"slide_delay_seconds", "autoplay", "loop"}


def test_config_values_come_from_the_singleton(api_client):
    HeroSliderConfig.objects.filter(pk=1).update(slide_delay_seconds=8, autoplay=False, loop=False)
    body = api_client.get(SLIDER).json()
    assert body["config"] == {"slide_delay_seconds": 8, "autoplay": False, "loop": False}


def test_only_active_in_schedule_banners_are_returned(api_client):
    now = timezone.now()
    visible = HeroBannerFactory(title="Visible")
    HeroBannerFactory(title="Inactive", is_active=False)
    HeroBannerFactory(title="Future", start_at=now + timedelta(days=1))
    body = api_client.get(SLIDER).json()
    assert len(body["banners"]) == 1
    assert body["banners"][0]["id"] == visible.id


def test_banner_shape_excludes_internal_fields(api_client):
    HeroBannerFactory(title="Internal Only", alt_text="Shop now")
    banner = api_client.get(SLIDER).json()["banners"][0]
    assert set(banner) == {
        "id", "desktop_image", "tablet_image", "mobile_image", "alt_text",
        "link_url", "link_target", "button_text", "slide_delay_override",
    }
    assert "title" not in banner and "is_active" not in banner and "sort_order" not in banner


def test_tablet_and_mobile_fall_back_to_desktop_in_the_response(api_client):
    HeroBannerFactory()
    banner = api_client.get(SLIDER).json()["banners"][0]
    assert banner["tablet_image"] == banner["desktop_image"] == banner["mobile_image"]


def test_own_tablet_and_mobile_images_are_used_when_set(api_client):
    HeroBannerFactory(tablet_image=make_image("t.png"), mobile_image=make_image("m.png"))
    banner = api_client.get(SLIDER).json()["banners"][0]
    assert banner["tablet_image"] != banner["desktop_image"]
    assert banner["mobile_image"] != banner["desktop_image"]
    assert banner["tablet_image"] != banner["mobile_image"]


def test_images_are_absolute_urls(api_client):
    HeroBannerFactory()
    assert api_client.get(SLIDER).json()["banners"][0]["desktop_image"].startswith("http://testserver/media/banners/")


def test_banners_are_ordered_by_sort_order(api_client):
    b = HeroBannerFactory(title="B", sort_order=2)
    a = HeroBannerFactory(title="A", sort_order=1)
    names_order = [x["id"] for x in api_client.get(SLIDER).json()["banners"]]
    assert names_order == [a.id, b.id]


def test_empty_slider_is_fine(api_client):
    body = api_client.get(SLIDER).json()
    assert body["banners"] == [] and body["config"]["slide_delay_seconds"] == 5


def test_stale_token_does_not_break_the_public_endpoint(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
    assert api_client.get(SLIDER).status_code == 200


def test_slider_is_read_only(api_client):
    for method in ("post", "put", "patch", "delete"):
        assert getattr(api_client, method)(SLIDER, {}, format="json").status_code == 405


def test_slider_served_from_cache_for_config(api_client, django_assert_max_num_queries):
    HeroBannerFactory()
    api_client.get(SLIDER)  # primes the config cache
    with django_assert_max_num_queries(3):
        assert api_client.get(SLIDER).status_code == 200
