"""Celery tasks for the catalog. Without Redis they run inline (CELERY_TASK_ALWAYS_EAGER), like the rest."""
from celery import shared_task

from . import services


@shared_task
def send_restock_alerts_task(product_id, variant_id=None):
    """Queued by `services.adjust_stock` when an item goes from 0 to in stock."""
    return services.send_restock_alerts(product_id, variant_id)
