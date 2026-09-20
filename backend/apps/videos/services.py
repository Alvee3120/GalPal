"""Video card business logic: visibility and safe deletion of the file(s) it owns."""

from django.db import transaction

from apps.core.utils import discard_file

from .models import VideoCard


def visible_videos():
    """Active video cards, in display order, with their (published) linked products prefetched."""
    from django.db.models import Prefetch

    from apps.catalog.models import Product

    return VideoCard.objects.filter(is_active=True).prefetch_related(
        Prefetch("products", queryset=Product.objects.filter(status="published"))
    )


@transaction.atomic
def delete_video(video):
    """Delete a video card and remove its file(s) from storage after commit."""
    files = [video.video_file, video.thumbnail]
    video.delete()
    for file in files:
        discard_file(file)
