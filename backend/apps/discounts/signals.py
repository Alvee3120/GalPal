"""Keeps the live-discount index (services._index) in step with every change that moves a price."""
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save

from apps.catalog.models import Category, ProductCategory

from . import services
from .models import Discount


def _refresh(**kwargs):
    services.invalidate()
    transaction.on_commit(services.invalidate)  # again once committed, so no worker keeps a mid-transaction view


for _sender in (Discount, ProductCategory, Category):
    post_save.connect(_refresh, sender=_sender, dispatch_uid=f"discount_index_save_{_sender.__name__}")
    post_delete.connect(_refresh, sender=_sender, dispatch_uid=f"discount_index_delete_{_sender.__name__}")
m2m_changed.connect(_refresh, sender=Discount.products.through, dispatch_uid="discount_index_products")
