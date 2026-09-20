from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import services
from .models import HeroSliderConfig


@receiver([post_save, post_delete], sender=HeroSliderConfig, dispatch_uid="hero_slider_config_cache_invalidate")
def invalidate_cache(sender, **kwargs):
    """Drop the cached config on every change (also covers the Django admin and shell edits)."""
    services.invalidate_slider_config_cache()
    transaction.on_commit(services.invalidate_slider_config_cache)
