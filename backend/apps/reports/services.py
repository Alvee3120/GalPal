"""
Admin reports (Module 17): the breakdowns shown on the Admin dashboard next to apps.orders.analytics, for its range.

Same business rules as the dashboard: a **sale** is a confirmed / processing / shipped / delivered order, valued at its
grand total; the **orders** count is every order placed in the range; dates are inclusive calendar days in the site's
time zone. Shipping figures use each order's own snapshot (`shipping_zone_name`, `shipping_charge`), so renaming or
re-pricing a zone later doesn't rewrite history. Nothing here changes data.
"""

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce

from apps.accounts.models import User
from apps.catalog.filters_product import IN_STOCK
from apps.catalog.models import Product
from apps.orders.analytics import LOW_STOCK, MONEY, SALE_STATUSES, ZERO, _stock_annotated
from apps.orders.models import Order, OrderSource
from apps.reviews.models import Review, ReviewStatus

IS_SALE = Q(status__in=SALE_STATUSES)
LOW_STOCK_LIMIT = 50


def _orders(date_from, date_to):
    return Order.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)


def _group(queryset, field):
    """orders / sale_orders / revenue per value of `field`, biggest revenue first."""
    return list(
        queryset.values(field)
        .annotate(
            orders=Count("id"),
            sale_orders=Count("id", filter=IS_SALE),
            revenue=Coalesce(Sum("grand_total", filter=IS_SALE), ZERO, output_field=MONEY),
        )
        .order_by("-revenue", "-orders")
    )


def by_source(orders):
    labels = dict(OrderSource.choices)
    return [{"source": r["source"], "label": labels.get(r["source"], r["source"]), **{k: r[k] for k in ("orders", "sale_orders", "revenue")}}
            for r in _group(orders, "source")]


def by_staff(orders):
    """Orders staff entered by hand (manual orders), per staff member who created them."""
    rows = _group(orders.filter(is_manual=True), "created_by")
    users = User.objects.in_bulk([r["created_by"] for r in rows if r["created_by"]])
    result = []
    for r in rows:
        user = users.get(r["created_by"])
        result.append({
            "user_id": r["created_by"],
            "name": user.full_name if user else "Former staff member",
            "role": user.get_role_display() if user else "",
            **{k: r[k] for k in ("orders", "sale_orders", "revenue")},
        })
    return result


def by_zone(orders):
    rows = (
        orders.values("shipping_zone_name")
        .annotate(
            orders=Count("id"),
            sale_orders=Count("id", filter=IS_SALE),
            shipping_revenue=Coalesce(Sum("shipping_charge", filter=IS_SALE), ZERO, output_field=MONEY),
            revenue=Coalesce(Sum("grand_total", filter=IS_SALE), ZERO, output_field=MONEY),
            free_shipping=Count("id", filter=IS_SALE & Q(shipping_charge=0)),
        )
        .order_by("-orders")
    )
    return [{"zone": r.pop("shipping_zone_name") or "No zone", **r} for r in rows]


def coupons(orders):
    rows = (
        orders.exclude(coupon_code="")
        .values("coupon_code")
        .annotate(
            orders=Count("id"),
            sale_orders=Count("id", filter=IS_SALE),
            discount=Coalesce(Sum("discount_amount", filter=IS_SALE), ZERO, output_field=MONEY),
            revenue=Coalesce(Sum("grand_total", filter=IS_SALE), ZERO, output_field=MONEY),
        )
        .order_by("-sale_orders", "-revenue")
    )
    return [{"code": r.pop("coupon_code"), **r} for r in rows]


def reviews(date_from, date_to):
    period = Review.objects.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    counts = period.aggregate(
        total=Count("id"),
        approved=Count("id", filter=Q(status=ReviewStatus.APPROVED)),
        pending=Count("id", filter=Q(status=ReviewStatus.PENDING)),
        rejected=Count("id", filter=Q(status=ReviewStatus.REJECTED)),
        average_rating=Avg("rating", filter=Q(status=ReviewStatus.APPROVED)),
    )
    avg = counts.pop("average_rating")
    return {
        **counts,
        "average_rating": round(float(avg), 2) if avg is not None else None,
        "awaiting_moderation": Review.objects.filter(status=ReviewStatus.PENDING).count(),  # now, not just this period
    }


def customers(date_from, date_to):
    all_customers = User.objects.filter(role=User.Role.CUSTOMER)
    new = all_customers.filter(created_at__date__gte=date_from, created_at__date__lte=date_to)
    return {
        "new": new.count(),
        "new_via_checkout": new.filter(created_via_checkout=True).count(),
        "total": all_customers.count(),
        "total_via_checkout": all_customers.filter(created_via_checkout=True).count(),
    }


def low_stock_products():
    """Published, still in stock, at or below the alert level — lowest first."""
    rows = [
        {"id": p.id, "name": p.name, "sku": p.sku, "has_variants": p.has_variants,
         "stock": p.variant_stock if p.has_variants else p.stock_quantity, "threshold": p.threshold}
        for p in _stock_annotated(Product.objects.filter(status="published")).filter(IN_STOCK & LOW_STOCK)
    ]
    return sorted(rows, key=lambda r: (r["stock"], r["name"]))[:LOW_STOCK_LIMIT]


def breakdowns(date_from, date_to):
    """
    The report sections shown on the Admin dashboard (GET /admin/dashboard/ → `reports`), for the dashboard's range:
    shipping/discount totals, by source, by staff member, by delivery zone, coupons, reviews, checkout-created
    accounts and the low-stock list. The dashboard itself already carries revenue, orders, the trend, statuses, top
    products, categories and customers.
    """
    orders = _orders(date_from, date_to)
    totals = orders.aggregate(
        shipping=Coalesce(Sum("shipping_charge", filter=IS_SALE), ZERO, output_field=MONEY),
        discount=Coalesce(Sum("discount_amount", filter=IS_SALE), ZERO, output_field=MONEY),
        manual=Count("id", filter=Q(is_manual=True)),
    )
    return {
        "summary": {"shipping_revenue": totals["shipping"], "discount_given": totals["discount"], "manual_orders": totals["manual"]},
        "by_source": by_source(orders),
        "by_staff": by_staff(orders),
        "by_zone": by_zone(orders),
        "coupons": coupons(orders),
        "reviews": reviews(date_from, date_to),
        "customers": customers(date_from, date_to),
        "low_stock": low_stock_products(),
    }
