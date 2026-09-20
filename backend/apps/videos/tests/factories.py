import io

import factory
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.videos.models import VideoCard


def make_image(name="thumb.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "pink").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue())


def make_video(name="clip.mp4"):
    return SimpleUploadedFile(name, b"\x00\x00\x00\x18ftypmp42" + b"0" * 100, content_type="video/mp4")


class VideoCardFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VideoCard

    title = factory.Sequence(lambda n: f"Video {n}")
    external_url = "https://youtube.com/watch?v=demo"
    thumbnail = factory.LazyFunction(make_image)
    is_active = True
    sort_order = 0
