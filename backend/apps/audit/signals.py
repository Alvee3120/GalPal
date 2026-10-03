"""
Event entries for the actions the spec names, hooked where they're recorded anyway so every path is covered:
orders created by staff (with the source chosen), status changes, order notes, and delivery-zone charge changes.
Shipping overrides and order edits are recorded by the order services themselves (with before/after).
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import OrderNote, OrderStatusHistory
from apps.shipping.models import ShippingChargeHistory

from . import services


@receiver(post_save, sender=OrderStatusHistory, dispatch_uid="audit_order_history")
def order_history(sender, instance, created, **kwargs):
    if not created:
        return
    actor = instance.changed_by
    order = instance.order
    if not instance.from_status:
        if not order.is_manual:
            return  # a customer's own checkout isn't a staff action
        services.record(
            "order.created", target=order, actor=actor,
            metadata={"source": order.source, "source_note": order.source_note, "grand_total": order.grand_total,
                      "payment_method": order.payment_method, "items": order.items.count()},
        )
    elif instance.from_status != instance.to_status:
        services.record(
            "order.status_changed", target=order, actor=actor,
            changes={"status": [instance.from_status, instance.to_status]},
            metadata={"note": instance.note, "source": order.source},
        )


@receiver(post_save, sender=OrderNote, dispatch_uid="audit_order_note")
def order_note(sender, instance, created, **kwargs):
    if created:
        services.record("order.note_added", target=instance.order, actor=instance.author, metadata={"text": instance.text[:1000]})


@receiver(post_save, sender=ShippingChargeHistory, dispatch_uid="audit_zone_charge")
def zone_charge(sender, instance, created, **kwargs):
    if created:
        services.record(
            "shipping.zone_charge_changed", target_type="deliveryzone", target_id=str(instance.zone_id or ""),
            target_label=instance.zone_name, actor=instance.changed_by,
            changes={"charge": [instance.old_charge, instance.new_charge]},
        )
