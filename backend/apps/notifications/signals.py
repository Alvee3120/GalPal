"""
Order notifications for every source (website checkout, staff/manual orders, customer cancels): driven by the
append-only OrderStatusHistory, whose first row ("" → pending) is the order being placed. Sent after the transaction
commits, so the order and its items are really there (and a rolled-back order sends nothing).
"""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import Order, OrderStatusHistory

from . import services


@receiver(post_save, sender=OrderStatusHistory, dispatch_uid="notifications_order_history")
def order_history_saved(sender, instance, created, **kwargs):
    if not created:
        return
    order_id, old, new = instance.order_id, instance.from_status, instance.to_status
    if old and old == new:
        return  # an edit / shipping override note, not a status change

    def send():
        order = Order.all_objects.filter(pk=order_id).select_related("customer").first()
        if order is None:
            return
        if not old:
            services.order_placed(order)
        else:
            services.order_status_changed(order, new)

    transaction.on_commit(send)
