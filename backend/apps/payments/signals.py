from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import Order

from .models import Payment, PaymentStatus


@receiver(post_save, sender=Order, dispatch_uid="payments_create_or_sync_payment")
def create_or_sync_payment(sender, instance, created, **kwargs):
    """
    Every order gets exactly one `Payment`, created the moment it's placed (storefront checkout or a
    staff-entered order — Module 10's code never needs to know this app exists). While nothing has
    been collected yet, an edit to a pending order's total (Module 10 lets staff edit items/address)
    keeps the amount owed in sync; once money has moved, the payment amount is frozen.
    """
    if created:
        Payment.objects.create(order=instance, method=instance.payment_method, amount=instance.grand_total)
        return
    payment = getattr(instance, "payment", None)
    if payment is None:
        return  # defensive: an order somehow saved without ever going through `created=True`
    if payment.amount_received == 0 and payment.status in (PaymentStatus.UNPAID, PaymentStatus.FAILED) and payment.amount != instance.grand_total:
        payment.amount = instance.grand_total
        payment.save(update_fields=["amount", "updated_at"])
