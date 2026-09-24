"""
Numbers for the staff dashboard overview (GET /admin/orders/dashboard/): current inventory, and sales / orders over
a date range. Everything is aggregated in the database; nothing here changes data.

Business rules (the same ones the rest of the order module uses):
* A **sale** is an order that is confirmed and still going ahead: confirmed, processing, shipped or delivered.
  Pending (not yet confirmed), cancelled, failed and returned orders are not sales — their stock has been, or will
  be, put back (`services.STOCK_RELEASING`). Sales are valued at the order's `grand_total`.
* The **orders** count is every order placed in the range, whatever its status.
* Dates are calendar days in the site's TIME_ZONE (Asia/Dhaka), inclusive, like `OrderFilter.date_from/date_to`.

Inventory (current, not historical) covers *published* products — the ones on sale — and follows how the storefront
decides availability (`apps.catalog.services._is_available`):
* a product without variants is in stock if it doesn't manage stock, is on backorder, or has quantity > 0;
* a product with variants is in stock if any active variant doesn't manage stock or has quantity > 0.
Inventory value = quantity on hand x the price it sells for right now (discount while the sale window is open),
per product, or per active variant (a variant's own price, else the product's) for products with variants. Stock
that isn't tracked has no quantity, so it adds nothing to the value.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, Exists, F, OuterRef, Q, Sum, When
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils import timezone

from apps.catalog.filters_product import annotate_effective_price
from apps.catalog.models import Product, ProductVariant, StockStatus

from .models import Order, OrderStatus

S = OrderStatus
SALE_STATUSES = (S.CONFIRMED, S.PROCESSING, S.SHIPPED, S.DELIVERED)
DEFAULT_DAYS = 30
DAILY_LIMIT_DAYS = 92  # longer ranges are grouped by month
MONEY = DecimalField(max_digits=14, decimal_places=2)
ZERO = Decimal("0.00")


def default_range(today=None):
    today = today or timezone.localdate()
    return today - timedelta(days=DEFAULT_DAYS - 1), today


# --- inventory -----------------------------------------------------------------------------------------------------


def _variant_in_stock():
    return ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True).filter(Q(manage_stock=False) | Q(stock_quantity__gt=0))


def inventory_summary():
    products = Product.objects.filter(status="published")
    simple_in_stock = Q(has_variants=False) & (Q(manage_stock=False) | Q(stock_status=StockStatus.BACKORDER) | Q(stock_quantity__gt=0))
    counts = products.annotate(any_variant_in_stock=Exists(_variant_in_stock())).aggregate(
        total=Count("id"),
        in_stock=Count("id", filter=simple_in_stock | (Q(has_variants=True) & Q(any_variant_in_stock=True))),
        untracked=Count("id", filter=Q(has_variants=False, manage_stock=False)),
    )

    simple_value = (
        annotate_effective_price(products.filter(has_variants=False, manage_stock=True, stock_quantity__gt=0))
        .aggregate(v=Sum(F("stock_quantity") * F("effective_price_db"), output_field=MONEY))["v"]
        or ZERO
    )

    now = timezone.now()
    window = (Q(product__sale_start_at__isnull=True) | Q(product__sale_start_at__lte=now)) & (
        Q(product__sale_end_at__isnull=True) | Q(product__sale_end_at__gte=now)
    )
    # Mirrors ProductVariant.effective_price: its own discount, else the product's discount when it has no own price.
    variant_price = Case(
        When(window & Q(discount_price__isnull=False), then=F("discount_price")),
        When(window & Q(regular_price__isnull=True, product__discount_price__isnull=False), then=F("product__discount_price")),
        default=Coalesce(F("regular_price"), F("product__regular_price")),
        output_field=MONEY,
    )
    variant_value = (
        ProductVariant.objects.filter(
            product__status="published", product__has_variants=True, product__is_deleted=False,
            is_active=True, manage_stock=True, stock_quantity__gt=0,
        )
        .annotate(price=variant_price)
        .aggregate(v=Sum(F("stock_quantity") * F("price"), output_field=MONEY))["v"]
        or ZERO
    )

    return {
        "total_products": counts["total"],
        "in_stock": counts["in_stock"],
        "out_of_stock": counts["total"] - counts["in_stock"],
        "untracked_products": counts["untracked"],
        "inventory_value": (simple_value + variant_value).quantize(Decimal("0.01")),
    }


# --- sales & orders over time ------------------------------------------------------------------------------------------


def _buckets(date_from, date_to, monthly):
    if monthly:
        current = date_from.replace(day=1)
        while current <= date_to:
            yield current
            current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        for offset in range((date_to - date_from).days + 1):
            yield date_from + timedelta(days=offset)


def sales_and_orders(date_from: date, date_to: date):
    orders = Order.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    is_sale = Q(status__in=SALE_STATUSES)

    totals = orders.aggregate(
        orders=Count("id"),
        sale_orders=Count("id", filter=is_sale),
        sales=Coalesce(Sum("grand_total", filter=is_sale), ZERO, output_field=MONEY),
    )
    by_status = {s: 0 for s in S.values}
    by_status.update(dict(orders.values_list("status").annotate(n=Count("id")).values_list("status", "n")))

    monthly = (date_to - date_from).days + 1 > DAILY_LIMIT_DAYS
    trunc = TruncMonth("created_at") if monthly else TruncDate("created_at")  # both in the current (site) time zone
    rows = (
        orders.annotate(bucket=trunc)
        .values("bucket")
        .annotate(orders=Count("id"), sales=Coalesce(Sum("grand_total", filter=is_sale), ZERO, output_field=MONEY))
    )
    # TruncMonth gives an aware datetime (local midnight on the 1st), TruncDate a date.
    found = {(row["bucket"].date() if isinstance(row["bucket"], datetime) else row["bucket"]): row for row in rows}
    series = [
        {"date": day.isoformat(), "orders": found.get(day, {}).get("orders", 0), "sales": found.get(day, {}).get("sales", ZERO)}
        for day in _buckets(date_from, date_to, monthly)
    ]

    sales = totals["sales"]
    return {
        "sales": {
            "total": sales,
            "orders": totals["sale_orders"],
            "average_order_value": (sales / totals["sale_orders"]).quantize(Decimal("0.01")) if totals["sale_orders"] else ZERO,
        },
        "orders": {"total": totals["orders"], "by_status": by_status},
        "granularity": "month" if monthly else "day",
        "series": series,
    }


def dashboard(date_from=None, date_to=None):
    if date_from is None or date_to is None:
        date_from, date_to = default_range()
    period = sales_and_orders(date_from, date_to)
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "granularity": period.pop("granularity"),
        "inventory": inventory_summary(),
        **period,
    }
