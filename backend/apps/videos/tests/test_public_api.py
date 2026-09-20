import pytest

from apps.catalog.tests.factories import ProductFactory

from .factories import VideoCardFactory, make_image, make_video

pytestmark = pytest.mark.django_db

VIDEOS = "/api/v1/videos/"


def test_only_active_videos_are_listed(api_client):
    visible = VideoCardFactory(title="Live")
    VideoCardFactory(title="Off", is_active=False)
    body = api_client.get(VIDEOS).json()
    assert body["count"] == 1 and body["results"][0]["id"] == visible.id


def test_response_shape_excludes_internal_fields(api_client):
    VideoCardFactory(title="Glow Routine")
    video = api_client.get(VIDEOS).json()["results"][0]
    assert set(video) == {"id", "title", "video_url", "thumbnail", "products"}
    assert "is_active" not in video and "sort_order" not in video and "external_url" not in video


def test_video_url_is_the_external_link_when_no_file(api_client):
    VideoCardFactory(external_url="https://youtube.com/watch?v=abc")
    assert api_client.get(VIDEOS).json()["results"][0]["video_url"] == "https://youtube.com/watch?v=abc"


def test_video_url_is_absolute_when_uploaded(api_client):
    VideoCardFactory(external_url="", video_file=make_video())
    url = api_client.get(VIDEOS).json()["results"][0]["video_url"]
    assert url.startswith("http://testserver/media/videos/")


def test_thumbnail_is_absolute_url(api_client):
    VideoCardFactory()
    assert api_client.get(VIDEOS).json()["results"][0]["thumbnail"].startswith("http://testserver/media/videos/")


def test_linked_products_show_card_data(api_client):
    video = VideoCardFactory()
    product = ProductFactory(name="Vitamin C Serum", regular_price="1200.00", discount_price="900.00")
    video.products.set([product])
    card = api_client.get(VIDEOS).json()["results"][0]["products"][0]
    assert set(card) == {"id", "name", "slug", "image", "price"}
    assert card["name"] == "Vitamin C Serum" and card["price"] == "900.00" and card["slug"] == product.slug


def test_draft_products_are_excluded_from_the_card_list(api_client):
    video = VideoCardFactory()
    draft = ProductFactory(status="draft")
    video.products.set([draft])
    assert api_client.get(VIDEOS).json()["results"][0]["products"] == []


def test_video_with_no_products_is_fine(api_client):
    VideoCardFactory()
    assert api_client.get(VIDEOS).json()["results"][0]["products"] == []


def test_videos_are_ordered_by_sort_order(api_client):
    b = VideoCardFactory(title="B", sort_order=2)
    a = VideoCardFactory(title="A", sort_order=1)
    order = [v["id"] for v in api_client.get(VIDEOS).json()["results"]]
    assert order == [a.id, b.id]


def test_list_is_paginated(api_client):
    VideoCardFactory.create_batch(3)
    body = api_client.get(VIDEOS).json()
    assert set(body) == {"count", "next", "previous", "results"} and body["count"] == 3


def test_stale_token_does_not_break_the_endpoint(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer garbage")
    assert api_client.get(VIDEOS).status_code == 200


def test_no_public_detail_route(api_client):
    video = VideoCardFactory()
    assert api_client.get(f"{VIDEOS}{video.id}/").status_code == 404


def test_endpoint_is_read_only(api_client):
    for method in ("post", "put", "patch", "delete"):
        assert getattr(api_client, method)(VIDEOS, {}, format="json").status_code == 405
