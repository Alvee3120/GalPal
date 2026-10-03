"""
CSV exports (Module 17): orders, products, customers. Streamed row by row so a big export doesn't sit in memory.

Cells that start with = + - @ (or a tab / carriage return) get a leading apostrophe, so a customer-typed name like
`=HYPERLINK(...)` opens as plain text in Excel / Sheets instead of running as a formula (CSV injection).
"""

import csv

from django.db.models import Count, Max, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.http import StreamingHttpResponse
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import Product, ProductCategory
from apps.orders.analytics import MONEY, SALE_STATUSES, ZERO
from apps.orders.models import Order

DANGEROUS_START = ("=", "+", "-", "@", "\t", "\r")


def safe(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value)
    return "'" + text if text.startswith(DANGEROUS_START) else text


def _local(dt):
    return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M") if dt else ""


class _Echo:
    def write(self, value):
        return value


def csv_response(filename, header, rows):
    writer = csv.writer(_Echo())

    def stream():
        yield "﻿"  # BOM: Excel reads the file as UTF-8 (৳, Bangla names)
        yield writer.writerow(header)
        for row in rows:
            yield writer.writerow([safe(cell) for cell in row])

    response = StreamingHttpResponse(stream(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


ORDER_HEADER = [
    "Order number", "Placed at", "Status", "Source", "Source note", "Created by", "Customer", "Phone", "Email",
    "Division", "District", "Area", "Address", "Items", "Units", "Subtotal", "Discount", "Coupon", "Shipping zone",
    "Delivery method", "Shipping charge", "Shipping overridden", "Tax", "Grand total", "Payment method",
    "Payment status", "Courier", "Tracking ID", "Parcel ID",
]


def order_rows(orders):
    orders = (
        orders.select_related("created_by")
        .annotate(line_count=Count("items"), units=Coalesce(Sum("items__quantity"), 0))
        .order_by("-created_at", "-id")
    )
    for o in orders.iterator(chunk_size=500):
        yield [
            o.number, _local(o.created_at), o.get_status_display(), o.get_source_display(), o.source_note,
            o.created_by.full_name if o.created_by else "", o.customer_name, o.phone, o.email,
            o.division, o.district, o.area, o.address_line, o.line_count, o.units, o.subtotal, o.discount_amount,
            o.coupon_code, o.shipping_zone_name, o.delivery_method_name, o.shipping_charge, o.shipping_overridden,
            o.tax_amount, o.grand_total, o.get_payment_method_display(), o.get_payment_status_display(),
            o.courier_name, o.tracking_id, o.consignment_id,
        ]


def export_orders(*, date_from, date_to, status=None, source=None):
    orders = Order.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    if status:
        orders = orders.filter(status=status)
    if source:
        orders = orders.filter(source=source)
    return csv_response(f"orders-{date_from}-to-{date_to}.csv", ORDER_HEADER, order_rows(orders))


PRODUCT_HEADER = [
    "Name", "SKU", "Barcode", "Status", "Brand", "Primary category", "Regular price", "Discount price", "Manage stock",
    "Stock quantity", "Stock status", "Has variants", "Active variants", "Variant stock", "Low stock alert at",
    "Featured", "New arrival", "Bestseller", "Average rating", "Reviews", "Created at",
]


def export_products():
    primary = ProductCategory.objects.filter(product_id=OuterRef("pk"), is_primary=True).values("category__name")[:1]
    products = (
        Product.objects.select_related("brand")
        .annotate(
            primary_category=Subquery(primary),
            active_variants=Count("variants", filter=Q(variants__is_active=True)),
            variant_stock=Coalesce(Sum("variants__stock_quantity", filter=Q(variants__is_active=True, variants__manage_stock=True)), 0),
        )
        .order_by("name")
    )

    def rows():
        for p in products.iterator(chunk_size=500):
            yield [
                p.name, p.sku, p.barcode, p.get_status_display(), p.brand.name if p.brand else "", p.primary_category or "",
                p.regular_price, p.discount_price, p.manage_stock, p.stock_quantity, p.get_stock_status_display(),
                p.has_variants, p.active_variants, p.variant_stock if p.has_variants else "",
                p.low_stock_threshold if p.low_stock_threshold is not None else "default", p.is_featured,
                p.is_new_arrival, p.is_bestseller, p.average_rating, p.review_count, _local(p.created_at),
            ]

    return csv_response(f"products-{timezone.localdate()}.csv", PRODUCT_HEADER, rows())


CUSTOMER_HEADER = [
    "Name", "Phone", "Email", "Joined", "Created at checkout", "Active", "Orders", "Confirmed orders",
    "Total spent (confirmed orders)", "Last order",
]


def export_customers(*, date_from=None, date_to=None):
    customers = User.objects.filter(role=User.Role.CUSTOMER)
    if date_from and date_to:
        customers = customers.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    live = Q(orders__is_deleted=False)  # soft-deleted orders don't count
    sale = live & Q(orders__status__in=SALE_STATUSES)
    customers = customers.annotate(
        order_count=Count("orders", filter=live),
        sale_count=Count("orders", filter=sale),
        spent=Coalesce(Sum("orders__grand_total", filter=sale), ZERO, output_field=MONEY),
        last_order=Max("orders__created_at", filter=live),
    ).order_by("-created_at")

    def rows():
        for c in customers.iterator(chunk_size=500):
            yield [
                c.full_name, c.phone, c.email, _local(c.created_at), c.created_via_checkout, c.is_active,
                c.order_count, c.sale_count, c.spent, _local(c.last_order),
            ]

    name = f"customers-{date_from}-to-{date_to}.csv" if date_from else f"customers-{timezone.localdate()}.csv"
    return csv_response(name, CUSTOMER_HEADER, rows())
