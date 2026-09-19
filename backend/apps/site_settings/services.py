"""Site settings business logic: cached reads, invalidation, and updates."""

import logging

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from .models import SiteSettings

logger = logging.getLogger(__name__)

CACHE_KEY = "site_settings:v1"
IMAGE_FIELDS = ("logo", "favicon", "default_og_image")


def invalidate_site_settings_cache():
    try:
        cache.delete(CACHE_KEY)
    except Exception:  # noqa: BLE001 - a cache outage must never break a save
        logger.warning("Could not invalidate the site settings cache", exc_info=True)


def get_site_settings():
    """
    The site settings row, served from cache.

    This is what every other module should call (checkout for `guest_checkout_enabled`, CAPI for
    tokens, ...). If the cache is down it falls back to the database, so a Redis outage
    degrades speed, never availability.
    """
    try:
        cached = cache.get(CACHE_KEY)
    except Exception:  # noqa: BLE001
        logger.warning("Site settings cache unavailable; reading from the database", exc_info=True)
        cached = None
    if cached is not None:
        return cached

    instance, _ = SiteSettings.objects.get_or_create(id=1)
    try:
        cache.set(CACHE_KEY, instance, settings.SITE_SETTINGS_CACHE_TTL)
    except Exception:  # noqa: BLE001
        logger.warning("Could not cache the site settings", exc_info=True)
    return instance


def update_site_settings(instance, *, user=None, **fields):
    """
    Apply `fields` to the singleton and save it. Replaced or cleared image files are removed
    from storage once the transaction commits (so a rollback never loses the old file).
    """
    with transaction.atomic():
        replaced = []
        for name, value in fields.items():
            if name in IMAGE_FIELDS:
                old = getattr(instance, name)
                if old and old.name and (value is None or value != old):
                    replaced.append((old.storage, old.name))
            setattr(instance, name, value)
        if user is not None:
            instance.updated_by = user
        instance.save()
        for storage, name in replaced:
            transaction.on_commit(lambda storage=storage, name=name: _delete_file(storage, name))
    return instance


def _delete_file(storage, name):
    try:
        storage.delete(name)
    except Exception:  # noqa: BLE001 - an orphaned file is not worth failing the request
        logger.warning("Could not delete replaced file %s", name, exc_info=True)
