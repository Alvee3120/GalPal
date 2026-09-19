from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import services
from .models import SiteSettings


@receiver([post_save, post_delete], sender=SiteSettings, dispatch_uid="site_settings_cache_invalidate")
def invalidate_cache(sender, **kwargs):
    """Drop the cached row on every change (also covers the Django admin and shell edits)."""
    services.invalidate_site_settings_cache()
    # Once more after commit: a concurrent request may have re-cached the old row in between.
    transaction.on_commit(services.invalidate_site_settings_cache)
