"""Cache invalidation for the catalog (Module 18): the cached category rows are dropped on every category change."""
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import services
from .models import Category


@receiver([post_save, post_delete], sender=Category, dispatch_uid="category_cache_invalidate")
def invalidate_categories(sender, **kwargs):
    services.invalidate_category_cache()
    transaction.on_commit(services.invalidate_category_cache)  # and again once committed (no stale re-fill mid-transaction)
