"""Small helpers shared across apps."""

import logging
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from slugify import slugify

logger = logging.getLogger(__name__)


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


def unique_slugify(
    model, value, *, instance=None, field="slug", fallback="item", max_length=None, reserved=()
):
    """
    Build a slug from `value` that is unique for `model.<field>`.

    Collisions get `-2`, `-3`, ... appended. Non-Latin text (e.g. Bangla) is
    transliterated; if nothing usable remains, `fallback` is used. Slugs in `reserved`
    (e.g. a route name like "tree") are treated as taken.

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
    while candidate in reserved or queryset.filter(**{field: candidate}).exists():
        counter += 1
        suffix = f"-{counter}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
    return candidate


def resolve_slug(
    model, *, name, slug=None, instance=None, name_changed=False, reserved=(), field="slug", fallback="item"
):
    """
    Decide the slug for a create/update and whether the admin set it by hand.
    Returns `(slug, is_custom)`.

    * create, no slug given      -> generated from `name`, `is_custom=False`
    * create, slug given         -> that slug (normalised), `is_custom=True`
    * update, slug not given (or unchanged) -> kept; but if the name changed and the slug was
      never set by hand, it is regenerated from the new name
    * update, slug changed       -> that slug, `is_custom=True`
    * update, slug "" (blank)    -> back to auto: regenerated from the name, `is_custom=False`

    A slug the admin types explicitly is never silently altered to avoid a clash: if it is
    taken (or reserved) a `ValidationError` on `slug` is raised. Only *generated* slugs get
    the `-2`, `-3` suffix.
    """
    max_length = model._meta.get_field(field).max_length
    was_custom = bool(getattr(instance, "slug_is_custom", False))
    current = getattr(instance, field, None) if instance is not None else None

    def auto():
        return unique_slugify(
            model, name, instance=instance, field=field, fallback=fallback, max_length=max_length, reserved=reserved
        ), False

    if slug is not None and slug.strip() == "":
        return auto()  # explicit blank = "switch back to automatic"

    normalized = slugify(slug, max_length=max_length) if slug is not None else None
    if slug is not None and not normalized:
        raise ValidationError({"slug": ["Enter a valid slug (letters, numbers and hyphens)."]})

    if normalized is None or (instance is not None and normalized == current):
        # nothing new from the admin
        if instance is None or (name_changed and not was_custom):
            return auto()
        return current, was_custom

    taken = model._base_manager.filter(**{field: normalized})
    if instance is not None and instance.pk is not None:
        taken = taken.exclude(pk=instance.pk)
    if normalized in reserved or taken.exists():
        raise ValidationError({"slug": ["This slug is already in use."]})
    return normalized, True


def discard_path(storage, name):
    """Delete `name` from `storage` once the surrounding transaction commits (now, if none)."""

    def _delete():
        try:
            storage.delete(name)
        except Exception:  # noqa: BLE001 - an orphaned file is not worth failing a request
            logger.warning("Could not delete file %s", name, exc_info=True)

    transaction.on_commit(_delete)


def discard_file(field_file):
    """
    Delete an uploaded file (a model `FieldFile`) after the transaction commits, so a rolled-back
    change never loses a file that is still referenced. No-op for an empty field.
    """
    if field_file and getattr(field_file, "name", None):
        discard_path(field_file.storage, field_file.name)


MASK = "\u2022" * 8  # ••••••••


def mask_secret(value):
    """
    Display form of a secret: "" if unset, otherwise bullets (plus the last 4 characters
    for long values, so an admin can tell two tokens apart). Never returns the full secret.
    """
    if not value:
        return ""
    return f"{MASK}{value[-4:]}" if len(value) >= 12 else MASK


def is_masked(value):
    """True if `value` looks like something `mask_secret` produced (i.e. a round-tripped mask)."""
    return isinstance(value, str) and value.startswith(MASK)
