import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.videos.models import VideoCard

from .factories import VideoCardFactory, make_image, make_video

pytestmark = pytest.mark.django_db


def test_defaults_and_str():
    video = VideoCardFactory(title="Glow Routine")
    assert str(video) == "Glow Routine" and video.is_active and video.sort_order == 0
    assert video.products.count() == 0


def test_video_url_prefers_uploaded_file():
    uploaded = VideoCardFactory(external_url="", video_file=make_video())
    assert uploaded.video_url == uploaded.video_file.url
    linked = VideoCardFactory(external_url="https://youtube.com/watch?v=x")
    assert linked.video_url == "https://youtube.com/watch?v=x"


def test_thumbnail_is_required():
    with pytest.raises(ValidationError):
        VideoCard(title="X", external_url="https://youtube.com/watch?v=x").full_clean()


def test_clean_rejects_both_sources():
    video = VideoCard(title="X", thumbnail=make_image(), video_file=make_video(), external_url="https://youtube.com/watch?v=x")
    with pytest.raises(ValidationError) as exc:
        video.clean()
    assert exc.value.code == "video_source_required"


def test_clean_rejects_neither_source():
    video = VideoCard(title="X", thumbnail=make_image())
    with pytest.raises(ValidationError):
        video.clean()


def test_database_rejects_both_sources_set():
    with pytest.raises(IntegrityError), transaction.atomic():
        VideoCardFactory(external_url="https://youtube.com/watch?v=x", video_file=make_video())


def test_database_rejects_neither_source_set():
    with pytest.raises(IntegrityError), transaction.atomic():
        VideoCardFactory(external_url="", video_file="")


def test_database_allows_exactly_one_source():
    VideoCardFactory(external_url="https://youtube.com/watch?v=x", video_file="")
    VideoCardFactory(external_url="", video_file=make_video())


def test_products_m2m():
    from apps.catalog.tests.factories import ProductFactory

    video = VideoCardFactory()
    a, b = ProductFactory(), ProductFactory()
    video.products.set([a, b])
    assert set(video.products.all()) == {a, b}
    assert set(a.videos.all()) == {video}


def test_ordering_is_sort_order_then_newest_first():
    old = VideoCardFactory(sort_order=1)
    new = VideoCardFactory(sort_order=1)
    first = VideoCardFactory(sort_order=0)
    assert list(VideoCard.objects.all()) == [first, new, old]
