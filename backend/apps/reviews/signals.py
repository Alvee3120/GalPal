from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import services
from .models import Review


@receiver([post_save, post_delete], sender=Review, dispatch_uid="reviews_recompute_product_rating")
def recompute_rating(sender, instance, **kwargs):
    """
    Recompute the product's `average_rating`/`review_count` on every save or delete of one of its
    reviews — covers a new review, a status change either way, an edited rating, and a deletion,
    including edits made from the Django admin or the shell.
    """
    product_id = instance.product_id
    services.recompute_product_rating(product_id)
    transaction.on_commit(lambda: services.recompute_product_rating(product_id))
