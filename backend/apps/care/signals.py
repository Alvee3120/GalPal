from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import Order

from . import services


@receiver(post_save, sender=Order, dispatch_uid="care_mark_checkout_leads_converted")
def mark_checkout_lead_converted(sender, instance, created, **kwargs):
    """A new order from a phone that had an open checkout lead: that checkout wasn't abandoned after all."""
    if created and instance.phone:
        services.mark_leads_converted(instance)
