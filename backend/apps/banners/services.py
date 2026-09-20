"""Hero slider business logic: cached config reads and banner visibility/ordering."""

import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from .models import HeroBanner, HeroSliderConfig

logger = logging.getLogger(__name__)

CACHE_KEY = "hero_slider_config:v1"
CACHE_TTL = getattr(settings, "SITE_SETTINGS_CACHE_TTL", 30)


def invalidate_slider_config_cache():
    try:
        cache.delete(CACHE_KEY)
    except Exception:  # noqa: BLE001 - a cache outage must never break a save
        logger.warning("Could not invalidate the hero slider config cache", exc_info=True)


def get_slider_config():
    """
    The slider-wide config, served from cache (same pattern as Module 2's site settings): a cache
    outage falls back to the database, so it degrades speed, never availability.
    """
    try:
        cached = cache.get(CACHE_KEY)
    except Exception:  # noqa: BLE001
        logger.warning("Hero slider config cache unavailable; reading from the database", exc_info=True)
        cached = None
    if cached is not None:
        return cached

    instance, _ = HeroSliderConfig.objects.get_or_create(id=1)
    try:
        cache.set(CACHE_KEY, instance, CACHE_TTL)
    except Exception:  # noqa: BLE001
        logger.warning("Could not cache the hero slider config", exc_info=True)
    return instance


def visible_banners():
    """Active banners within their schedule window, in display order."""
    now = timezone.now()
    return HeroBanner.objects.filter(
        Q(is_active=True)
        & (Q(start_at__isnull=True) | Q(start_at__lte=now))
        & (Q(end_at__isnull=True) | Q(end_at__gte=now))
    ).order_by("sort_order", "-created_at")


def reorder_banners(ids):
    """
    Set `sort_order` from the position of each id in `ids`.

    `ids` must be exactly the current set of banner ids (no more, no fewer) — raises
    `ValueError` otherwise, so a stale or partial list can't silently drop banners from the order.
    """
    banners = {banner.pk: banner for banner in HeroBanner.objects.all()}
    if set(ids) != set(banners):
        raise ValueError("Must list exactly the current banner ids, in the new order.")
    for order, banner_id in enumerate(ids):
        banners[banner_id].sort_order = order
    HeroBanner.objects.bulk_update(banners.values(), ["sort_order"])
    return list(banners[i] for i in ids)
