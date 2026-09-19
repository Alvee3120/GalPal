"""Small helpers shared across apps."""

import uuid
from pathlib import Path

from django.utils import timezone
from django.utils.deconstruct import deconstructible
from slugify import slugify


@deconstructible
class UploadPath:
    """
    `upload_to` for file fields: `<folder>/<YYYY>/<MM>/<random>.<ext>`.

        image = models.ImageField(upload_to=UploadPath("products"))

    Random file names avoid collisions and never trust user-supplied names.
    Folders in use: products/, categories/, banners/, videos/.
    (A class rather than a closure so migrations can serialize it.)
    """

    def __init__(self, folder):
        self.folder = folder.strip("/")

    def __call__(self, instance, filename):
        extension = Path(filename).suffix.lower()
        return f"{self.folder}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{extension}"


def unique_slugify(model, value, *, instance=None, field="slug", fallback="item", max_length=None):
    """
    Build a slug from `value` that is unique for `model.<field>`.

    Collisions get `-2`, `-3`, ... appended. Non-Latin text (e.g. Bangla) is
    transliterated; if nothing usable remains, `fallback` is used.

    All rows count, including soft-deleted ones, because the database unique
    constraint does. Pass `instance` when updating so it doesn't collide with itself.
    Two simultaneous requests can still pick the same slug; the unique constraint is
    the final guard, callers may retry on IntegrityError.
    """
    max_length = max_length or model._meta.get_field(field).max_length
    base = slugify(value or "", max_length=max_length) or fallback

    queryset = model._base_manager.all()
    if instance is not None and instance.pk is not None:
        queryset = queryset.exclude(pk=instance.pk)

    candidate, counter = base, 1
    while queryset.filter(**{field: candidate}).exists():
        counter += 1
        suffix = f"-{counter}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
    return candidate
