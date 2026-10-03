"""Business logic for Module 15: newsletter sign-up/opt-out, live announcements, and the global storefront search."""

import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from apps.catalog.filters_product import annotate_effective_price
from apps.catalog.models import Brand, Category, Product, ProductStatus
from apps.catalog.services import CategoryIndex
from apps.core.validators import normalize_bd_phone

from .exceptions import field_error
from .models import Announcement, NewsletterSubscriber

# The storefront pages backed by a CMS page of the same slug. Each has a built-in fallback on the storefront, so a
# missing or inactive page never 404s; any other slug is served at /pages/<slug>.
STANDARD_PAGES = {
    "about": "About Us",
    "privacy-policy": "Privacy Policy",
    "terms": "Terms of Service",
    "return-and-cancellation-policy": "Return & Cancellation Policy",
    "shipping-policy": "Shipping Policy",
}

SAFE_LINK = re.compile(r"^(/(?!/)|https?://)", re.IGNORECASE)


def clean_link(value, field="link_url"):
    """A site path ("/shop") or an http(s) URL — never `javascript:` or protocol-relative `//host` links."""
    value = (value or "").strip()
    if value and not SAFE_LINK.match(value):
        raise field_error(field, "Use a site path like /shop or a full http(s):// link.", "invalid")
    return value


# --- newsletter ----------------------------------------------------------------------------------------------------------


def subscribe(*, email="", phone="", source="", ip_address=None):
    """
    Signs someone up (or back up). Matches an existing subscriber by email or phone so nobody is listed twice. The
    response is the same whether they were new, already subscribed or returning — it never reveals who is on the list.
    """
    email = (email or "").strip().lower() or None
    phone = (phone or "").strip() or None
    if not email and not phone:
        raise field_error("email", "Enter your email or phone number.", "required")
    if phone:
        try:
            phone = normalize_bd_phone(phone)
        except ValidationError:
            raise field_error("phone", "Enter a valid Bangladeshi mobile number, e.g. 01712345678.", "invalid") from None

    match = Q()
    if email:
        match |= Q(email=email)
    if phone:
        match |= Q(phone=phone)
    try:
        with transaction.atomic():
            sub = NewsletterSubscriber.objects.select_for_update().filter(match).first()
            if sub is None:
                return NewsletterSubscriber.objects.create(email=email, phone=phone, source=source[:30], ip_address=ip_address)
            changed = []
            if email and not sub.email and not NewsletterSubscriber.objects.filter(email=email).exists():
                sub.email = email
                changed.append("email")
            if phone and not sub.phone and not NewsletterSubscriber.objects.filter(phone=phone).exists():
                sub.phone = phone
                changed.append("phone")
            if not sub.is_subscribed:
                sub.is_subscribed, sub.unsubscribed_at = True, None
                changed += ["is_subscribed", "unsubscribed_at"]
            if changed:
                sub.save(update_fields=[*changed, "updated_at"])
            return sub
    except IntegrityError:  # a simultaneous sign-up with the same address won the race — that's the same outcome
        return NewsletterSubscriber.objects.filter(match).first()


def unsubscribe(token):
    """Opts out the subscriber holding this link token. Returns False for an unknown token."""
    token = (token or "").strip()
    if not token:
        return False
    updated = NewsletterSubscriber.objects.filter(token=token).update(
        is_subscribed=False, unsubscribed_at=timezone.now(), updated_at=timezone.now()
    )
    return bool(updated)


def set_subscribed(sub, subscribed):
    """Admin switch for one subscriber."""
    if sub.is_subscribed != subscribed:
        sub.is_subscribed = subscribed
        sub.unsubscribed_at = None if subscribed else timezone.now()
        sub.save(update_fields=["is_subscribed", "unsubscribed_at", "updated_at"])
    return sub


# --- announcements -------------------------------------------------------------------------------------------------------


def live_announcements():
    now = timezone.now()
    return Announcement.objects.filter(is_active=True).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now), Q(ends_at__isnull=True) | Q(ends_at__gt=now)
    )


# --- global search -------------------------------------------------------------------------------------------------------

SEARCH_MIN_LENGTH = 2
SEARCH_MAX_LENGTH = 100


def _starts_first(field, q):
    return Case(When(**{f"{field}__istartswith": q}, then=Value(0)), default=Value(1), output_field=IntegerField())


def global_search(q, *, limit=6):
    """
    Published products, visible categories and active brands matching `q`, best (name starts with `q`) first, plus up
    to 8 `suggestions` (distinct names) for autocomplete. Queries shorter than 2 characters return nothing.
    """
    q = " ".join((q or "").split())[:SEARCH_MAX_LENGTH]
    empty = {"query": q, "products": [], "product_count": 0, "categories": [], "brands": [], "suggestions": []}
    if len(q) < SEARCH_MIN_LENGTH:
        return empty

    product_match = Product.objects.filter(status=ProductStatus.PUBLISHED).filter(
        Q(name__icontains=q) | Q(sku__iexact=q) | Q(brand__name__icontains=q) | Q(tags__name__icontains=q)
    )
    product_ids = product_match.values("pk").distinct()
    products = annotate_effective_price(
        Product.objects.filter(pk__in=product_ids)
        .select_related("brand")
        .prefetch_related("category_links__category", "variants")
        .annotate(rank=_starts_first("name", q))
    ).order_by("rank", "name")
    product_count = Product.objects.filter(pk__in=product_ids).count()

    categories = (
        Category.objects.filter(pk__in=CategoryIndex().visible_ids(), name__icontains=q)
        .annotate(rank=_starts_first("name", q))
        .order_by("rank", "sort_order", "name")[:limit]
    )
    brands = Brand.objects.filter(is_active=True, name__icontains=q).annotate(rank=_starts_first("name", q)).order_by("rank", "name")[:limit]

    products, categories, brands = list(products[:limit]), list(categories), list(brands)
    suggestions, seen = [], set()
    for name in sorted((x.name for x in [*categories, *brands, *products]), key=lambda n: (not n.lower().startswith(q.lower()), len(n))):
        if name.lower() not in seen:
            seen.add(name.lower())
            suggestions.append(name)
    return {
        "query": q, "products": products, "product_count": product_count,
        "categories": categories, "brands": brands, "suggestions": suggestions[:8],
    }
