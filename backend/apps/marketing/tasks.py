"""
Celery tasks. `send_meta_event_task`/`send_ga4_event_task` do the actual HTTP call (via `services`)
and retry themselves on a transient failure; `dispatch_purchase_event` is the entry point the
`Order` signal enqueues, and re-reads the order fresh (rather than being handed a stale snapshot),
so a retried dispatch always reflects the order's current state.
"""
import requests
from celery import shared_task

from . import services

RETRY_KWARGS = dict(autoretry_for=(requests.RequestException,), max_retries=3, retry_backoff=True, retry_backoff_max=300, retry_jitter=True)


@shared_task(bind=True, **RETRY_KWARGS)
def send_meta_event_task(self, *, event_name, event_id="", user_data, custom_data=None, event_source_url="", order_id=None, user_id=None, is_manual_order=False):
    order, user = _resolve(order_id, user_id)
    services.send_meta_event(
        event_name=event_name, event_id=event_id, user_data=user_data, custom_data=custom_data,
        event_source_url=event_source_url, order=order, user=user, is_manual_order=is_manual_order,
        attempt=self.request.retries + 1,
    )


@shared_task(bind=True, **RETRY_KWARGS)
def send_ga4_event_task(self, *, event_name, client_id, params=None, order_id=None, user_id=None, is_manual_order=False):
    order, user = _resolve(order_id, user_id)
    services.send_ga4_event(
        event_name=event_name, client_id=client_id, params=params, order=order, user=user,
        is_manual_order=is_manual_order, attempt=self.request.retries + 1,
    )


@shared_task
def dispatch_purchase_event(order_id):
    """The one thing the `Order` signal enqueues: builds the Purchase payload from the order as it
    is right now, and hands each destination to its own retryable task."""
    from apps.orders.models import Order
    from apps.site_settings.services import get_site_settings

    order = Order.objects.select_related("customer").prefetch_related("items").get(pk=order_id)
    site = get_site_settings()
    items = list(order.items.all())

    user_data = services.build_user_data(user=order.customer, email=order.email, phone=order.phone, name=order.customer_name)
    event_id = f"order-{order.number}"  # deterministic: also what the frontend's browser-pixel Purchase event should use to dedupe

    send_meta_event_task.delay(
        event_name="Purchase", event_id=event_id, user_data=user_data, order_id=order.pk, user_id=order.customer_id,
        is_manual_order=order.is_manual,
        custom_data={
            "currency": site.currency_code, "value": str(order.grand_total),
            "content_ids": [item.sku for item in items],
            "contents": [{"id": item.sku, "quantity": item.quantity, "item_price": str(item.unit_price)} for item in items],
            "num_items": order.item_count,
        },
    )
    send_ga4_event_task.delay(
        event_name="Purchase", client_id=str(order.customer_id or order.phone), order_id=order.pk, user_id=order.customer_id,
        is_manual_order=order.is_manual,
        params={
            "currency": site.currency_code, "value": float(order.grand_total), "transaction_id": order.number,
            "items": [{"item_id": i.sku, "item_name": i.product_name, "quantity": i.quantity, "price": float(i.unit_price)} for i in items],
        },
    )


def _resolve(order_id, user_id):
    order = user = None
    if order_id:
        from apps.orders.models import Order

        order = Order.objects.filter(pk=order_id).first()
    if user_id:
        from apps.accounts.models import User

        user = User.objects.filter(pk=user_id).first()
    return order, user
