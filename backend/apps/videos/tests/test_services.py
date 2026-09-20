import pytest
from django.core.files.storage import default_storage

from apps.videos import services
from apps.videos.models import VideoCard

from .factories import VideoCardFactory, make_image, make_video

pytestmark = pytest.mark.django_db


def test_visible_excludes_inactive():
    visible = VideoCardFactory(is_active=True)
    VideoCardFactory(is_active=False)
    assert list(services.visible_videos()) == [visible]


def test_visible_prefetches_only_published_products():
    from apps.catalog.tests.factories import ProductFactory

    video = VideoCardFactory()
    published = ProductFactory(status="published")
    draft = ProductFactory(status="draft")
    video.products.set([published, draft])
    result = services.visible_videos().get(pk=video.pk)
    assert list(result.products.all()) == [published]


def test_delete_removes_files_after_commit(django_capture_on_commit_callbacks):
    video = VideoCardFactory(external_url="", video_file=make_video())
    video_path, thumb_path = video.video_file.name, video.thumbnail.name
    with django_capture_on_commit_callbacks(execute=True):
        services.delete_video(video)
    assert not VideoCard.objects.filter(pk=video.pk).exists()
    assert not default_storage.exists(video_path) and not default_storage.exists(thumb_path)


def test_delete_does_not_touch_products():
    from apps.catalog.tests.factories import ProductFactory

    video = VideoCardFactory()
    product = ProductFactory()
    video.products.set([product])
    services.delete_video(video)
    assert ProductFactory._meta.model.objects.filter(pk=product.pk).exists()
