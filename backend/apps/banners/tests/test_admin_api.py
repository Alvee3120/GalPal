from datetime import timedelta

import pytest
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.banners.models import HeroBanner, HeroSliderConfig

from .factories import HeroBannerFactory, make_image

pytestmark = pytest.mark.django_db

CONFIG = "/api/v1/admin/hero-slider-config/"
BANNERS = "/api/v1/admin/hero-banners/"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


def details(response):
    return response.json()["error"]["details"]


def minimal_payload(**overrides):
    payload = {"title": "Summer Sale", "desktop_image": make_image()}
    payload.update(overrides)
    return payload


# --- access control -------------------------------------------------------------------------------


@pytest.mark.parametrize("url", [CONFIG, BANNERS])
def test_anonymous_is_401(api_client, url):
    assert api_client.get(url).status_code == 401


@pytest.mark.parametrize("url", [CONFIG, BANNERS])
def test_customer_and_cce_get_403(auth_client, customer, cce_user, url):
    for user in (customer, cce_user):
        client = auth_client(user)
        assert client.get(url).status_code == 403
        assert client.post(url, {}, format="json").status_code == 403


def test_cce_cannot_reorder_or_delete_banners(auth_client, cce_user):
    banner = HeroBannerFactory()
    client = auth_client(cce_user)
    assert client.post(f"{BANNERS}reorder/", [banner.id], format="json").status_code == 403
    assert client.delete(f"{BANNERS}{banner.id}/").status_code == 403


# --- slider config ---------------------------------------------------------------------------------


def test_admin_reads_config(admin_client):
    body = admin_client.get(CONFIG).json()
    assert body == {"slide_delay_seconds": 5, "autoplay": True, "loop": True, "updated_at": body["updated_at"]}


def test_admin_updates_config(admin_client):
    r = admin_client.patch(CONFIG, {"slide_delay_seconds": 10, "autoplay": False}, format="json")
    assert r.status_code == 200 and r.json()["slide_delay_seconds"] == 10 and r.json()["autoplay"] is False
    assert HeroSliderConfig.objects.get().loop is True  # untouched


def test_config_delay_range_is_validated(admin_client):
    assert admin_client.patch(CONFIG, {"slide_delay_seconds": 0}, format="json").status_code == 400
    assert admin_client.patch(CONFIG, {"slide_delay_seconds": 200}, format="json").status_code == 400


def test_config_change_is_visible_publicly_right_away(admin_client, api_client):
    api_client.get("/api/v1/hero-banners/")  # primes the cache
    admin_client.patch(CONFIG, {"slide_delay_seconds": 15}, format="json")
    assert api_client.get("/api/v1/hero-banners/").json()["config"]["slide_delay_seconds"] == 15


def test_config_only_get_and_patch(admin_client):
    assert admin_client.post(CONFIG, {}, format="json").status_code == 405
    assert admin_client.delete(CONFIG).status_code == 405


# --- banner CRUD -------------------------------------------------------------------------------------


def test_create_minimal_banner(admin_client):
    r = admin_client.post(BANNERS, minimal_payload(), format="multipart")
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Summer Sale" and body["is_active"] is True
    assert body["desktop_image"].startswith("http://testserver/media/banners/")
    assert body["tablet_image"] is None and body["mobile_image"] is None


def test_desktop_image_required_on_create(admin_client):
    r = admin_client.post(BANNERS, {"title": "X"}, format="multipart")
    assert r.status_code == 400 and "desktop_image" in details(r)


def test_create_with_all_fields(admin_client):
    now = timezone.now()
    payload = minimal_payload(
        tablet_image=make_image("t.png"), mobile_image=make_image("m.png"), alt_text="Shop now",
        link_url="https://example.com/sale", link_target="_blank", button_text="Shop Now",
        sort_order=3, slide_delay_override=8,
        start_at=now.isoformat(), end_at=(now + timedelta(days=7)).isoformat(),
    )
    r = admin_client.post(BANNERS, payload, format="multipart")
    assert r.status_code == 201
    body = r.json()
    assert body["link_url"] == "https://example.com/sale" and body["link_target"] == "_blank"
    assert body["button_text"] == "Shop Now" and body["sort_order"] == 3 and body["slide_delay_override"] == 8


def test_link_url_must_be_http(admin_client):
    r = admin_client.post(BANNERS, minimal_payload(link_url="javascript:alert(1)"), format="multipart")
    assert r.status_code == 400 and "link_url" in details(r)


def test_end_at_must_be_after_start_at(admin_client):
    now = timezone.now()
    r = admin_client.post(BANNERS, minimal_payload(start_at=now.isoformat(), end_at=now.isoformat()), format="multipart")
    assert r.status_code == 400 and "end_at" in details(r)


def test_list_includes_inactive_and_shows_visibility(admin_client):
    HeroBannerFactory(title="Live", is_active=True)
    HeroBannerFactory(title="Off", is_active=False)
    body = admin_client.get(BANNERS).json()
    assert body["count"] == 2
    by_title = {b["title"]: b["is_currently_visible"] for b in body["results"]}
    assert by_title == {"Live": True, "Off": False}


def test_filter_search_and_ordering(admin_client):
    HeroBannerFactory(title="Winter Sale", is_active=False)
    HeroBannerFactory(title="Summer Sale", is_active=True)
    client = admin_client
    assert client.get(f"{BANNERS}?is_active=false").json()["count"] == 1
    assert [b["title"] for b in client.get(f"{BANNERS}?search=winter").json()["results"]] == ["Winter Sale"]


def test_retrieve_and_404(admin_client):
    banner = HeroBannerFactory()
    assert admin_client.get(f"{BANNERS}{banner.id}/").json()["id"] == banner.id
    assert admin_client.get(f"{BANNERS}99999/").status_code == 404


def test_patch_updates_scalar_fields(admin_client):
    banner = HeroBannerFactory(title="Old")
    r = admin_client.patch(f"{BANNERS}{banner.id}/", {"title": "New", "is_active": False}, format="json")
    assert r.status_code == 200 and r.json()["title"] == "New" and r.json()["is_active"] is False


def test_patch_replacing_desktop_image_deletes_the_old_file(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        banner_id = admin_client.post(BANNERS, minimal_payload(), format="multipart").json()["id"]
    old_name = HeroBanner.objects.get(pk=banner_id).desktop_image.name
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.patch(f"{BANNERS}{banner_id}/", {"desktop_image": make_image("new.png")}, format="multipart")
    new_name = HeroBanner.objects.get(pk=banner_id).desktop_image.name
    assert new_name != old_name and default_storage.exists(new_name) and not default_storage.exists(old_name)


def test_patch_without_images_keeps_them(admin_client):
    banner = HeroBannerFactory(tablet_image=make_image())
    tablet_name = banner.tablet_image.name
    admin_client.patch(f"{BANNERS}{banner.id}/", {"title": "Renamed"}, format="json")
    banner.refresh_from_db()
    assert banner.tablet_image.name == tablet_name


def test_delete_removes_files(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        banner_id = admin_client.post(
            BANNERS, minimal_payload(tablet_image=make_image("t.png")), format="multipart"
        ).json()["id"]
    banner = HeroBanner.objects.get(pk=banner_id)
    desktop_name, tablet_name = banner.desktop_image.name, banner.tablet_image.name
    with django_capture_on_commit_callbacks(execute=True):
        assert admin_client.delete(f"{BANNERS}{banner_id}/").status_code == 204
    assert not default_storage.exists(desktop_name) and not default_storage.exists(tablet_name)
    assert not HeroBanner.objects.filter(pk=banner_id).exists()


def test_put_not_supported(admin_client):
    banner = HeroBannerFactory()
    assert admin_client.put(f"{BANNERS}{banner.id}/", {}, format="json").status_code == 405


def test_invalid_image_is_rejected(admin_client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    bad = SimpleUploadedFile("x.gif", b"GIF87a" + b"0" * 20)
    r = admin_client.post(BANNERS, minimal_payload(desktop_image=bad), format="multipart")
    assert r.status_code == 400 and "desktop_image" in details(r)


# --- reorder --------------------------------------------------------------------------------------


def test_reorder_success(admin_client):
    a, b, c = HeroBannerFactory(), HeroBannerFactory(), HeroBannerFactory()
    r = admin_client.post(f"{BANNERS}reorder/", [c.id, a.id, b.id], format="json")
    assert r.status_code == 200
    assert [x["id"] for x in r.json()] == [c.id, a.id, b.id]
    a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()
    assert (c.sort_order, a.sort_order, b.sort_order) == (0, 1, 2)


def test_reorder_rejects_mismatched_ids(admin_client):
    a = HeroBannerFactory()
    r = admin_client.post(f"{BANNERS}reorder/", [a.id, 999999], format="json")
    assert r.status_code == 400
