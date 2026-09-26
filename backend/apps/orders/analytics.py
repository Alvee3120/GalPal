"""
Numbers for the staff dashboards: the CCE overview (GET /admin/orders/dashboard/, `dashboard`) and the Admin overview
(GET /admin/dashboard/, `admin_dashboard`, a superset). Current inventory, and sales / orders over a date range.
Everything is aggregated in the database; nothing here changes data.

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
that isn't tracked has no quantity, so it adds nothing to the value. Low stock uses the product's own
`low_stock_threshold`, else Site Settings' `low_stock_threshold` (as `Product.is_low_stock` does); for a product with
variants it's the total across its active, tracked variants.

Time series are grouped by hour for a single day, by day up to 62 days, by 7-day week (starting on the range's first
day) up to 182 days, and by month beyond that.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, Exists, F, IntegerField, Max, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDate, TruncHour, TruncMonth
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.filters_product import IN_STOCK, annotate_effective_price, variant_in_stock_subquery
from apps.catalog.models import Product, ProductCategory, ProductVariant, StockStatus
from apps.site_settings.services import get_site_settings

from .models import Order, OrderItem, OrderStatus

S = OrderStatus
SALE_STATUSES = (S.CONFIRMED, S.PROCESSING, S.SHIPPED, S.DELIVERED)
DEFAULT_DAYS = 30
DAILY_LIMIT_DAYS = 62  # up to this many days: one point per day
WEEKLY_LIMIT_DAYS = 182  # up to this many: 7-day weeks; beyond: months
MONEY = DecimalField(max_digits=14, decimal_places=2)
ZERO = Decimal("0.00")


def default_range(today=None):
    today = today or timezone.localdate()
    return today - timedelta(days=DEFAULT_DAYS - 1), today


# --- inventory -----------------------------------------------------------------------------------------------------


def _stock_annotated(products):
    """Annotate what the stock rules need: any variant in stock, untracked variants, tracked variant total, threshold."""
    active = ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True)
    variant_total = active.filter(manage_stock=True).values("product").annotate(t=Sum("stock_quantity")).values("t")
    return products.annotate(
        any_variant_in_stock=Exists(variant_in_stock_subquery()),
        any_variant_untracked=Exists(active.filter(manage_stock=False)),
        variant_stock=Coalesce(Subquery(variant_total, output_field=IntegerField()), Value(0)),
        threshold=Coalesce(F("low_stock_threshold"), Value(get_site_settings().low_stock_threshold)),
    )


LOW_STOCK = (
    Q(has_variants=False, manage_stock=True, stock_quantity__gt=0, stock_quantity__lte=F("threshold")) & ~Q(stock_status=StockStatus.BACKORDER)
) | Q(has_variants=True, any_variant_untracked=False, variant_stock__gt=0, variant_stock__lte=F("threshold"))


def inventory_summary():
    products = Product.objects.filter(status="published")
    counts = _stock_annotated(products).aggregate(
        total=Count("id"),
        in_stock=Count("id", filter=IN_STOCK),
        low_stock=Count("id", filter=IN_STOCK & LOW_STOCK),
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
        "low_stock": counts["low_stock"],
        "untracked_products": counts["untracked"],
        "inventory_value": (simple_value + variant_value).quantize(Decimal("0.01")),
    }


# --- sales & orders over time ------------------------------------------------------------------------------------------


def granularity_for(date_from, date_to):
    days = (date_to - date_from).days + 1
    if days == 1:
        return "hour"
    if days <= DAILY_LIMIT_DAYS:
        return "day"
    return "week" if days <= WEEKLY_LIMIT_DAYS else "month"


def _months(date_from, date_to):
    current = date_from.replace(day=1)
    while current <= date_to:
        yield current
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)


def time_series(orders, date_from, date_to):
    """[{date, end?, orders, sales}] with every bucket present (zeros included), plus the granularity used."""
    granularity = granularity_for(date_from, date_to)
    is_sale = Q(status__in=SALE_STATUSES)
    trunc = {"hour": TruncHour("created_at"), "month": TruncMonth("created_at")}.get(granularity, TruncDate("created_at"))
    rows = (
        orders.annotate(bucket=trunc)  # truncation happens in the current (site) time zone
        .values("bucket")
        .annotate(orders=Count("id"), sales=Coalesce(Sum("grand_total", filter=is_sale), ZERO, output_field=MONEY))
    )
    found = {}
    for row in rows:
        bucket = row["bucket"]
        if granularity == "hour":
            key = timezone.localtime(bucket).hour
        else:
            key = bucket.date() if isinstance(bucket, datetime) else bucket
        found[key] = row

    def point(label, keys, end=None):
        entry = {"date": label, "orders": sum(found.get(k, {}).get("orders", 0) for k in keys),
                 "sales": sum((found.get(k, {}).get("sales", ZERO) for k in keys), ZERO)}
        if end:
            entry["end"] = end
        return entry

    if granularity == "hour":
        series = [point(f"{date_from.isoformat()}T{h:02d}:00", [h]) for h in range(24)]
    elif granularity == "month":
        series = [point(m.isoformat(), [m]) for m in _months(date_from, date_to)]
    else:
        days = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
        if granularity == "day":
            series = [point(d.isoformat(), [d]) for d in days]
        else:  # 7-day weeks from the first day of the range; the last one may be shorter
            series = [point(days[i].isoformat(), days[i:i + 7], end=days[min(i + 6, len(days) - 1)].isoformat()) for i in range(0, len(days), 7)]
    return granularity, series


def _orders_in(date_from, date_to):
    return Order.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)


def sales_and_orders(date_from: date, date_to: date):
    orders = _orders_in(date_from, date_to)
    is_sale = Q(status__in=SALE_STATUSES)

    totals = orders.aggregate(
        orders=Count("id"),
        sale_orders=Count("id", filter=is_sale),
        sales=Coalesce(Sum("grand_total", filter=is_sale), ZERO, output_field=MONEY),
    )
    by_status = {s: 0 for s in S.values}
    by_status.update(dict(orders.values_list("status").annotate(n=Count("id")).values_list("status", "n")))
    granularity, series = time_series(orders, date_from, date_to)

    sales = totals["sales"]
    return {
        "sales": {
            "total": sales,
            "orders": totals["sale_orders"],
            "average_order_value": (sales / totals["sale_orders"]).quantize(Decimal("0.01")) if totals["sale_orders"] else ZERO,
        },
        "orders": {"total": totals["orders"], "by_status": by_status},
        "granularity": granularity,
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


# --- Admin overview (a superset of the CCE one) ----------------------------------------------------------------------------

TOP_LIMIT = 5
RECENT_LIMIT = 6
CATEGORY_LIMIT = 6


def _sold_items(date_from, date_to):
    """Order lines of sales (confirmed/processing/shipped/delivered orders) placed in the range."""
    return OrderItem.objects.filter(
        order__created_at__date__gte=date_from, order__created_at__date__lte=date_to, order__status__in=SALE_STATUSES
    )


def _headline(date_from, date_to):
    """The four period figures that get a previous-period comparison."""
    orders = _orders_in(date_from, date_to).aggregate(
        count=Count("id"), revenue=Coalesce(Sum("grand_total", filter=Q(status__in=SALE_STATUSES)), ZERO, output_field=MONEY)
    )
    return {
        "revenue": orders["revenue"],
        "orders": orders["count"],
        "products_sold": _sold_items(date_from, date_to).aggregate(n=Coalesce(Sum("quantity"), 0))["n"],
        "new_customers": User.objects.filter(
            role=User.Role.CUSTOMER, created_at__date__gte=date_from, created_at__date__lte=date_to
        ).count(),
    }


def _change(current, previous):
    """Percent change vs the previous period, or None when there's nothing to compare against (previous = 0)."""
    if not previous:
        return None
    return round(float((Decimal(current) - Decimal(previous)) / Decimal(previous) * 100), 1)


def _media_url(field, absolute):
    if not field:
        return None
    try:
        url = field.url
    except ValueError:
        return None
    return absolute(url) if url.startswith("/") else url


def top_products(date_from, date_to, absolute):
    """Best sellers by units sold: variants roll up into their product; revenue is the lines' total (item prices)."""
    rows = list(
        _sold_items(date_from, date_to).exclude(product__isnull=True)
        .values("product_id")
        .annotate(name=Max("product_name"), sold=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-sold", "-revenue")[:TOP_LIMIT]
    )
    products = Product.all_objects.in_bulk([r["product_id"] for r in rows])
    result = []
    for row in rows:
        product = products.get(row["product_id"])
        result.append({
            "product_id": row["product_id"],
            "name": product.name if product else row["name"],
            "slug": product.slug if product else None,
            "image": _media_url(product.feature_image, absolute) if product else None,
            "sold": row["sold"],
            "revenue": row["revenue"],
        })
    return result


def category_sales(date_from, date_to):
    """Item revenue and units by each product's primary category; lines without one fall into "Uncategorized"."""
    items = _sold_items(date_from, date_to)
    overall = items.aggregate(revenue=Coalesce(Sum("line_total"), ZERO, output_field=MONEY), units=Coalesce(Sum("quantity"), 0))
    primary = ProductCategory.objects.filter(product_id=OuterRef("product_id"), is_primary=True).values("category__name")[:1]
    rows = list(
        items.annotate(category=Subquery(primary)).exclude(category__isnull=True)
        .values("category")
        .annotate(revenue=Sum("line_total"), units=Sum("quantity"))
        .order_by("-revenue")
    )
    categorized = sum((r["revenue"] for r in rows), ZERO)
    categorized_units = sum(r["units"] for r in rows)
    shown = [{"name": r["category"], "revenue": r["revenue"], "units": r["units"]} for r in rows[:CATEGORY_LIMIT]]
    rest = rows[CATEGORY_LIMIT:]
    if rest:
        shown.append({"name": "Other categories", "revenue": sum((r["revenue"] for r in rest), ZERO), "units": sum(r["units"] for r in rest)})
    uncategorized = overall["revenue"] - categorized
    if uncategorized > 0:
        shown.append({"name": "Uncategorized", "revenue": uncategorized, "units": overall["units"] - categorized_units})
    return {"total": overall["revenue"], "categories": shown}


def recent_orders(date_from, date_to):
    rows = _orders_in(date_from, date_to).order_by("-created_at", "-id")[:RECENT_LIMIT]
    return [
        {"id": o.id, "number": o.number, "customer_name": o.customer_name, "created_at": o.created_at,
         "grand_total": o.grand_total, "status": o.status}
        for o in rows
    ]


def out_of_stock_products(absolute, limit=5):
    rows = (
        _stock_annotated(Product.objects.filter(status="published")).exclude(IN_STOCK)
        .order_by("-updated_at")[:limit]
    )
    return [
        {"id": p.id, "name": p.name, "sku": p.sku, "image": _media_url(p.feature_image, absolute),
         "has_variants": p.has_variants, "stock_status": p.stock_status}
        for p in rows
    ]


def customer_summary(date_from, date_to):
    """Account-holding customers: total, new in the period, and who ordered in it (first-time vs returning)."""
    customers = User.objects.filter(role=User.Role.CUSTOMER)
    ordered = set(
        _orders_in(date_from, date_to).exclude(customer__isnull=True).values_list("customer_id", flat=True).distinct()
    )
    returning = set(
        Order.objects.filter(customer_id__in=ordered, created_at__date__lt=date_from).values_list("customer_id", flat=True).distinct()
    )
    return {
        "total": customers.count(),
        "new": customers.filter(created_at__date__gte=date_from, created_at__date__lte=date_to).count(),
        "ordering": len(ordered),
        "returning": len(returning),
        "first_time": len(ordered) - len(returning),
    }


def admin_dashboard(date_from=None, date_to=None, *, absolute=lambda url: url):
    """
    The Admin overview for one date range: headline figures with a comparison to the immediately preceding period
    of the same length, the CCE numbers (inventory, sales/orders, per-status counts, time series), and best sellers,
    category sales, recent orders, out-of-stock products and customers. `absolute` turns a relative media URL into
    an absolute one (the view passes request.build_absolute_uri).
    """
    base = dashboard(date_from, date_to)
    date_from, date_to = date.fromisoformat(base["date_from"]), date.fromisoformat(base["date_to"])
    length = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=length - 1)

    current, previous = _headline(date_from, date_to), _headline(prev_from, prev_to)
    headline = {key: {"value": current[key], "previous": previous[key], "change": _change(current[key], previous[key])} for key in current}

    return {
        **base,
        "previous_period": {"date_from": prev_from.isoformat(), "date_to": prev_to.isoformat()},
        "headline": headline,
        "top_products": top_products(date_from, date_to, absolute),
        "category_sales": category_sales(date_from, date_to),
        "recent_orders": recent_orders(date_from, date_to),
        "out_of_stock_products": out_of_stock_products(absolute),
        "customers": customer_summary(date_from, date_to),
    }
