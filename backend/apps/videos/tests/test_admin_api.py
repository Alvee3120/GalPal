import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.catalog.tests.factories import ProductFactory
from apps.videos.models import VideoCard

from .factories import VideoCardFactory, make_image, make_video

pytestmark = pytest.mark.django_db

VIDEOS = "/api/v1/admin/videos/"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


def details(response):
    return response.json()["error"]["details"]


def minimal_payload(**overrides):
    payload = {"title": "Glow Routine", "external_url": "https://youtube.com/watch?v=demo", "thumbnail": make_image()}
    payload.update(overrides)
    return payload


# --- access control -------------------------------------------------------------------------------


def test_anonymous_is_401(api_client):
    assert api_client.get(VIDEOS).status_code == 401


def test_customer_and_cce_get_403(auth_client, customer, cce_user):
    for user in (customer, cce_user):
        client = auth_client(user)
        assert client.get(VIDEOS).status_code == 403
        assert client.post(VIDEOS, {}, format="json").status_code == 403


def test_cce_cannot_delete(auth_client, cce_user):
    video = VideoCardFactory()
    assert auth_client(cce_user).delete(f"{VIDEOS}{video.id}/").status_code == 403


# --- create -----------------------------------------------------------------------------------


def test_create_with_external_url(admin_client):
    r = admin_client.post(VIDEOS, minimal_payload(), format="multipart")
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Glow Routine" and body["video_url"] == "https://youtube.com/watch?v=demo"
    assert body["thumbnail"].startswith("http://testserver/media/videos/")
    assert body["products"] == []


def test_create_with_uploaded_file(admin_client):
    r = admin_client.post(VIDEOS, minimal_payload(external_url="", video_file=make_video()), format="multipart")
    assert r.status_code == 201
    assert r.json()["video_url"].startswith("http://testserver/media/videos/")


def test_thumbnail_is_required(admin_client):
    payload = minimal_payload()
    del payload["thumbnail"]
    r = admin_client.post(VIDEOS, payload, format="multipart")
    assert r.status_code == 400 and "thumbnail" in details(r)


def test_both_sources_rejected(admin_client):
    r = admin_client.post(VIDEOS, minimal_payload(video_file=make_video()), format="multipart")
    assert r.status_code == 400 and "non_field_errors" in details(r)


def test_neither_source_rejected(admin_client):
    r = admin_client.post(VIDEOS, minimal_payload(external_url=""), format="multipart")
    assert r.status_code == 400 and "non_field_errors" in details(r)


def test_external_url_must_be_http(admin_client):
    r = admin_client.post(VIDEOS, minimal_payload(external_url="javascript:alert(1)"), format="multipart")
    assert r.status_code == 400 and "external_url" in details(r)


def test_uploaded_video_must_be_mp4_or_webm(admin_client):
    bad = SimpleUploadedFile("x.avi", b"not a video")
    r = admin_client.post(VIDEOS, minimal_payload(external_url="", video_file=bad), format="multipart")
    assert r.status_code == 400 and "video_file" in details(r)


def test_video_content_rejected_even_with_a_good_extension(admin_client):
    fake = SimpleUploadedFile("x.mp4", b"not actually a video")
    r = admin_client.post(VIDEOS, minimal_payload(external_url="", video_file=fake), format="multipart")
    assert r.status_code == 400 and "video_file" in details(r)


def test_oversized_video_is_rejected(admin_client, settings):
    settings.VIDEO_MAX_UPLOAD_SIZE = 10
    r = admin_client.post(VIDEOS, minimal_payload(external_url="", video_file=make_video()), format="multipart")
    assert r.status_code == 400 and "video_file" in details(r)


def test_invalid_thumbnail_is_rejected(admin_client):
    bad = SimpleUploadedFile("x.png", b"<html>nope</html>")
    r = admin_client.post(VIDEOS, minimal_payload(thumbnail=bad), format="multipart")
    assert r.status_code == 400 and "thumbnail" in details(r)


def test_create_with_linked_products(admin_client):
    a, b = ProductFactory(), ProductFactory()
    r = admin_client.post(VIDEOS, minimal_payload(product_ids=[a.id, b.id]), format="multipart")
    assert r.status_code == 201
    ids = {p["id"] for p in r.json()["products"]}
    assert ids == {a.id, b.id}
    assert set(r.json()["products"][0]) == {"id", "name", "sku", "feature_image"}


def test_create_with_unknown_product_id_is_400(admin_client):
    r = admin_client.post(VIDEOS, minimal_payload(product_ids=[999999]), format="multipart")
    assert r.status_code == 400 and "product_ids" in details(r)


# --- read / list -------------------------------------------------------------------------------------


def test_list_includes_inactive(admin_client):
    VideoCardFactory(is_active=True)
    VideoCardFactory(is_active=False)
    assert admin_client.get(VIDEOS).json()["count"] == 2


def test_filter_search_and_ordering(admin_client):
    VideoCardFactory(title="Winter Routine", is_active=False)
    VideoCardFactory(title="Summer Routine", is_active=True)
    assert admin_client.get(f"{VIDEOS}?is_active=false").json()["count"] == 1
    assert [v["title"] for v in admin_client.get(f"{VIDEOS}?search=winter").json()["results"]] == ["Winter Routine"]


def test_retrieve_and_404(admin_client):
    video = VideoCardFactory()
    assert admin_client.get(f"{VIDEOS}{video.id}/").json()["id"] == video.id
    assert admin_client.get(f"{VIDEOS}99999/").status_code == 404


# --- update ------------------------------------------------------------------------------------------


def test_patch_updates_scalar_fields(admin_client):
    video = VideoCardFactory(title="Old")
    r = admin_client.patch(f"{VIDEOS}{video.id}/", {"title": "New", "is_active": False}, format="json")
    assert r.status_code == 200 and r.json()["title"] == "New" and r.json()["is_active"] is False


def test_patch_replaces_linked_products(admin_client):
    a, b = ProductFactory(), ProductFactory()
    video = VideoCardFactory()
    video.products.set([a])
    r = admin_client.patch(f"{VIDEOS}{video.id}/", {"product_ids": [b.id]}, format="json")
    assert {p["id"] for p in r.json()["products"]} == {b.id}


def test_patch_omitting_products_leaves_them_unchanged(admin_client):
    a = ProductFactory()
    video = VideoCardFactory()
    video.products.set([a])
    admin_client.patch(f"{VIDEOS}{video.id}/", {"title": "Renamed"}, format="json")
    assert set(video.products.values_list("id", flat=True)) == {a.id}


def test_patch_switching_from_url_to_upload(admin_client):
    video = VideoCardFactory()
    r = admin_client.patch(f"{VIDEOS}{video.id}/", {"external_url": "", "video_file": make_video()}, format="multipart")
    assert r.status_code == 200 and r.json()["video_url"].startswith("http://testserver/media/videos/")


def test_patch_replacing_thumbnail_deletes_the_old_file(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        video_id = admin_client.post(VIDEOS, minimal_payload(), format="multipart").json()["id"]
    old_name = VideoCard.objects.get(pk=video_id).thumbnail.name
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.patch(f"{VIDEOS}{video_id}/", {"thumbnail": make_image("new.png")}, format="multipart")
    new_name = VideoCard.objects.get(pk=video_id).thumbnail.name
    assert new_name != old_name and default_storage.exists(new_name) and not default_storage.exists(old_name)


def test_delete_removes_files(admin_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        video_id = admin_client.post(VIDEOS, minimal_payload(external_url="", video_file=make_video()), format="multipart").json()["id"]
    video = VideoCard.objects.get(pk=video_id)
    video_name, thumb_name = video.video_file.name, video.thumbnail.name
    with django_capture_on_commit_callbacks(execute=True):
        assert admin_client.delete(f"{VIDEOS}{video_id}/").status_code == 204
    assert not default_storage.exists(video_name) and not default_storage.exists(thumb_name)
    assert not VideoCard.objects.filter(pk=video_id).exists()


def test_put_not_supported(admin_client):
    video = VideoCardFactory()
    assert admin_client.put(f"{VIDEOS}{video.id}/", {}, format="json").status_code == 405


# --- product picker (spec ties this to Module 6) --------------------------------------------------------


PICKER = "/api/v1/admin/products/picker/"


def test_picker_returns_published_products_only(admin_client):
    published = ProductFactory(status="published")
    ProductFactory(status="draft")
    body = admin_client.get(PICKER).json()
    assert {p["id"] for p in body} == {published.id}
    assert set(body[0]) == {"id", "name", "sku", "feature_image"}


def test_picker_search(admin_client):
    match = ProductFactory(name="Vitamin C Serum")
    ProductFactory(name="Face Wash")
    assert {p["id"] for p in admin_client.get(f"{PICKER}?search=vitamin").json()} == {match.id}
    assert {p["id"] for p in admin_client.get(f"{PICKER}?search={match.sku}").json()} == {match.id}


def test_picker_is_capped_at_20_and_search_still_works_past_the_cap(admin_client):
    for i in range(25):
        ProductFactory(name=f"Bulk Item {i}")
    needle = ProductFactory(name="Needle Product")
    assert len(admin_client.get(PICKER).json()) == 20
    assert {p["id"] for p in admin_client.get(f"{PICKER}?search=needle").json()} == {needle.id}


def test_picker_is_admin_only(api_client, auth_client, customer, cce_user):
    assert api_client.get(PICKER).status_code == 401
    assert auth_client(customer).get(PICKER).status_code == 403
    assert auth_client(cce_user).get(PICKER).status_code == 403


def test_picker_is_not_paginated(admin_client):
    ProductFactory()
    assert isinstance(admin_client.get(PICKER).json(), list)
