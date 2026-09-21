from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import services
from .models import DeliveryMethod, DeliveryZone, District, ZoneDistrict


@receiver(
    [post_save, post_delete], sender=DeliveryZone, dispatch_uid="shipping_zone_cache_invalidate"
)
@receiver(
    [post_save, post_delete], sender=ZoneDistrict, dispatch_uid="shipping_coverage_cache_invalidate"
)
@receiver(
    [post_save, post_delete], sender=DeliveryMethod, dispatch_uid="shipping_method_cache_invalidate"
)
@receiver(
    [post_save, post_delete], sender=District, dispatch_uid="shipping_district_cache_invalidate"
)
def invalidate_cache(sender, **kwargs):
    """Drop the cached index on every change, including Django-admin and shell edits that skip services."""
    services.invalidate_cache()
    transaction.on_commit(services.invalidate_cache)
