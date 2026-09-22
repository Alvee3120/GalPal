from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import Order
from apps.site_settings.services import get_site_settings

from .tasks import dispatch_purchase_event


@receiver(post_save, sender=Order, dispatch_uid="marketing_purchase_event")
def fire_purchase_event(sender, instance, created, **kwargs):
    """
    Purchase is the one event this app fires on its own, for every order the instant it's placed —
    storefront checkout (`source="website"`) always; a staff-entered order only if Site Settings'
    "Send manual orders to CAPI" is on. Dispatched after commit, so a checkout that fails after this
    signal (a later step in the same transaction raising) never reports a sale that didn't happen.
    """
    if not created:
        return
    if instance.is_manual and not get_site_settings().send_manual_orders_to_capi:
        return
    transaction.on_commit(lambda: dispatch_purchase_event.delay(instance.pk))
