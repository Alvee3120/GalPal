"""
Shipping business logic: zone lookup (cached), the delivery-charge calculation, and every write
to zones (default-zone rules, coverage, charge history).

Everything that decides money lives here, on a *cached snapshot* of the active zones
(`get_index`), so a checkout or cart page doesn't hit the database for it. The snapshot is dropped
on any change (signals + explicit calls), so an Admin's new charge applies to the next calculation.
If the cache is down it is rebuilt from the database: an outage costs speed, never correctness.
"""
import logging
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from apps.site_settings.services import get_site_settings

from .exceptions import ShippingNotConfigured, field_error
from .models import DeliveryZone, District, ShippingChargeHistory, ZoneDistrict, format_estimated_days

logger = logging.getLogger(__name__)

CACHE_KEY = "shipping:index:v2"  # v2: zones carry `area_names`
MONEY = Decimal("0.01")

REASON_THRESHOLD = "free_shipping_threshold"
REASON_COUPON = "coupon_free_shipping"


# --- matching text ------------------------------------------------------------------------------------


def normalize_name(value):
    """
    A comparable form of a district/area name: case, punctuation and spacing don't matter, and a
    trailing "district" is ignored ("Cox's  Bazar", "coxs bazar" and "COX'S BAZAR" are one name).
    """
    text = re.sub(r"[’'`.]", "", str(value or "").casefold())
    text = " ".join(re.sub(r"[-_,/]+", " ", text).split())
    return text[: -len(" district")] if text.endswith(" district") else text


# --- the cached index ---------------------------------------------------------------------------------


def invalidate_cache():
    try:
        cache.delete(CACHE_KEY)
    except Exception:  # noqa: BLE001 - a cache outage must never break a save
        logger.warning("Could not invalidate the shipping cache", exc_info=True)


def _build_index():
    from .models import DeliveryMethod  # local: keeps the module importable while models load

    zones = []
    queryset = DeliveryZone.objects.filter(is_active=True).prefetch_related("coverage__district")
    for zone in queryset:
        coverage = [(link.district_id, {normalize_name(a) for a in link.areas}) for link in zone.coverage.all()]
        zones.append({
            "id": zone.id, "name": zone.name, "slug": zone.slug, "charge": zone.charge,
            "estimated_days": zone.estimated_days, "free_shipping_threshold": zone.free_shipping_threshold,
            "is_default": zone.is_default, "sort_order": zone.sort_order,
            "districts": [link.district.name for link in zone.coverage.all()],
            # As the Admin typed them, for pickers (e.g. checkout's Dhaka zone list); matching uses `coverage`.
            "area_names": [{"district": link.district.name, "areas": list(link.areas)} for link in zone.coverage.all() if link.areas],
            "coverage": coverage,
        })
    district_ids = {}
    for district in District.objects.all():
        for name in [district.name, *district.aliases]:
            district_ids[normalize_name(name)] = district.id
    methods = [
        {"id": m.id, "slug": m.slug, "name": m.name, "description": m.description,
         "extra_charge": m.extra_charge, "estimated_days": m.estimated_days_label}
        for m in DeliveryMethod.objects.filter(is_active=True)
    ]
    return {"zones": zones, "district_ids": district_ids, "methods": methods}


def get_index():
    """The active zones, district lookup and active methods, from cache (DB fallback)."""
    try:
        cached = cache.get(CACHE_KEY)
    except Exception:  # noqa: BLE001
        logger.warning("Shipping cache unavailable; reading from the database", exc_info=True)
        cached = None
    if cached is not None:
        return cached
    index = _build_index()
    try:
        cache.set(CACHE_KEY, index, settings.SHIPPING_CACHE_TTL)
    except Exception:  # noqa: BLE001
        logger.warning("Could not cache the shipping index", exc_info=True)
    return index


def effective_threshold(zone):
    """The subtotal that makes this zone free: its own override, else the global one; None = never."""
    override = zone["free_shipping_threshold"]
    threshold = override if override is not None else get_site_settings().free_shipping_threshold
    return threshold if threshold and threshold > 0 else None


def public_zones():
    """Active zones for the storefront, in display order, each with its effective free-shipping threshold."""
    return [
        {**zone, "free_shipping_threshold": effective_threshold(zone)}
        for zone in sorted(get_index()["zones"], key=lambda z: (z["sort_order"], z["id"]))
    ]


def public_methods():
    return list(get_index()["methods"])


# --- resolving a zone ---------------------------------------------------------------------------------


def resolve_zone(district, area="", *, index=None):
    """
    The zone for an address. A zone naming the address's area wins; else the zone covering the whole
    district; else the default zone. Unknown or misspelt districts land on the default zone too.
    """
    index = index or get_index()
    district_id = index["district_ids"].get(normalize_name(district))
    if district_id is not None:
        area_key = normalize_name(area)
        whole_district = None
        for zone in index["zones"]:
            for covered_id, areas in zone["coverage"]:
                if covered_id != district_id:
                    continue
                if not areas:
                    whole_district = whole_district or zone
                elif area_key and area_key in areas:
                    return zone
        if whole_district is not None:
            return whole_district
    default = next((z for z in index["zones"] if z["is_default"]), None)
    if default is None:
        raise ShippingNotConfigured()
    return default


# --- the calculation ----------------------------------------------------------------------------------


def _address_part(address, name):
    return (address.get(name) if isinstance(address, dict) else getattr(address, name, "")) or ""


def calculate_shipping(address, cart_subtotal, coupon=None, *, delivery_method=None):
    """
    The delivery charge for an address and a cart subtotal. Always computed here, on the server;
    checkout stores the result as a snapshot on the order and never accepts a client-sent charge.

    `address`: a dict or object with `district` (and optionally `area`).
    `cart_subtotal`: the cart's item total *before* any coupon discount.
    `coupon`: the cart's applied coupon, or None. The caller must only pass one that is currently
              valid (checkout has just redeemed it; the cart endpoint checks `is_valid`) — only its
              `free_shipping` flag is read here.
    `delivery_method`: an active method's slug, or None for the plain zone charge.

    Steps: resolve zone -> base charge (+ method extra) -> free if the subtotal reaches the
    threshold (zone override, else the global one) -> free if the coupon grants free shipping.
    When shipping is free the whole charge is zero, method extra included.
    """
    index = get_index()
    zone = resolve_zone(_address_part(address, "district"), _address_part(address, "area"), index=index)
    method = _resolve_method(delivery_method, index)

    zone_charge = zone["charge"]
    method_extra = method["extra_charge"] if method else Decimal("0.00")
    charge = zone_charge + method_extra

    subtotal = _money(cart_subtotal)
    threshold = effective_threshold(zone)
    reason = None
    if threshold is not None and subtotal >= threshold:
        reason = REASON_THRESHOLD
    elif coupon is not None and getattr(coupon, "free_shipping", False):
        reason = REASON_COUPON
    if reason:
        charge = Decimal("0.00")

    return {
        "zone_id": zone["id"],
        "zone_name": zone["name"],
        "charge": charge.quantize(MONEY),
        "is_free": reason is not None,
        "free_shipping_reason": reason,
        "estimated_days": (method["estimated_days"] if method and method["estimated_days"] else zone["estimated_days"]),
        "zone_charge": zone_charge,
        "delivery_method": (
            {"id": method["id"], "slug": method["slug"], "name": method["name"], "extra_charge": method["extra_charge"]}
            if method else None
        ),
        "free_shipping_threshold": threshold,
    }


def _money(value):
    try:
        amount = Decimal(str(value)).quantize(MONEY)
    except (InvalidOperation, ValueError):
        amount = None
    if amount is None or not amount.is_finite() or amount < 0:
        raise field_error("subtotal", "A valid, non-negative amount is required.", "invalid")
    return amount


def _resolve_method(slug, index):
    if not slug:
        return None
    method = next((m for m in index["methods"] if m["slug"] == slug), None)
    if method is None:
        raise field_error("delivery_method", "This delivery method is not available.", "invalid_delivery_method")
    return method


# --- admin writes -------------------------------------------------------------------------------------
# None of these invalidate the cache by hand: every write goes through `save()`/`delete()` on a zone,
# method or district, and `signals.invalidate_cache` drops the index for each (again after commit, so a
# concurrent reader can't re-cache the old values while the transaction is still open).


class InvalidCharge(ValueError):
    """A charge that fails `check_charge`; carries a machine `code` alongside the message."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message, self.code = message, code


def check_charge(value):
    """
    A charge as a 2-place Decimal, or `InvalidCharge`: it must be a number, not negative and no larger
    than `SHIPPING_MAX_CHARGE` (a guard against a stray extra zero). Serializers turn the exception
    into a field error; `validate_charge` turns it into a `ValidationError` for service callers.
    """
    try:
        amount = Decimal(str(value)).quantize(MONEY)
    except (InvalidOperation, ValueError):
        raise InvalidCharge("A valid amount is required.", "invalid") from None
    if not amount.is_finite():  # "NaN" survives quantize() and then blows up on comparison
        raise InvalidCharge("A valid amount is required.", "invalid")
    if amount < 0:
        raise InvalidCharge("The charge cannot be negative.", "negative_charge")
    maximum = Decimal(str(settings.SHIPPING_MAX_CHARGE))
    if amount > maximum:
        raise InvalidCharge(f"The charge cannot exceed {maximum}.", "charge_too_high")
    return amount


def validate_charge(value, field="charge"):
    try:
        return check_charge(value)
    except InvalidCharge as exc:
        raise field_error(field, exc.message, exc.code) from None


def has_orders(obj):
    """
    True if any order references this zone/method. There is no Order model yet (Module 10): its
    `shipping_zone` / `delivery_method` foreign keys must use `related_name="orders"`, which this
    picks up without importing the orders app. Deleting is blocked while it's true.
    """
    manager = getattr(obj, "orders", None)
    return manager is not None and manager.exists()


def _record_charge(zone, old, new, user):
    ShippingChargeHistory.objects.create(
        zone=zone, zone_name=zone.name, old_charge=old, new_charge=new, changed_by=user if user and user.pk else None
    )


@transaction.atomic
def change_charge(zone, new_charge, *, user=None):
    """Change only a zone's charge (the admin "change delivery fee" field) and log it. Returns the zone."""
    new_charge = validate_charge(new_charge)
    zone = DeliveryZone.objects.select_for_update().get(pk=zone.pk)
    old = zone.charge
    if new_charge != old:
        zone.charge = new_charge
        zone.save(update_fields=["charge", "updated_at"])
        _record_charge(zone, old, new_charge, user)
    return zone


@transaction.atomic
def save_zone(zone, *, coverage=None, user=None):
    """
    Save a new or edited zone (already populated in memory) while keeping the default-zone rules:
    exactly one default; it can't be unset (make another zone the default instead) or deactivated;
    marking a zone default demotes the previous one in the same transaction. `coverage` is a list of
    `{"district_id", "areas"}` replacing the zone's districts, or None to leave them alone. A charge
    change (or the initial charge) is written to the history.
    """
    is_new = zone.pk is None
    previous = None if is_new else DeliveryZone.objects.select_for_update().get(pk=zone.pk)

    if previous is not None and previous.is_default and not zone.is_default:
        raise field_error(
            "is_default", "Every store needs a default zone. Make another zone the default instead.", "default_zone_required"
        )
    if zone.is_default and not zone.is_active:
        raise field_error("is_active", "The default zone cannot be deactivated.", "default_zone_inactive")
    if zone.is_default and (previous is None or not previous.is_default):
        list(DeliveryZone.objects.select_for_update().filter(is_default=True))  # serialise concurrent swaps
        DeliveryZone.objects.filter(is_default=True).exclude(pk=zone.pk).update(is_default=False)

    if coverage is not None:
        coverage = validate_coverage(zone, coverage)
    zone.save()
    if coverage is not None:
        _replace_coverage(zone, coverage)

    old_charge = None if previous is None else previous.charge
    if old_charge != zone.charge:
        _record_charge(zone, old_charge, zone.charge, user)
    return zone


def validate_coverage(zone, items):
    """
    Check a zone's district list and return it cleaned: known districts, no district twice, and no
    clash with another zone (a district has one whole-district zone; two zones can't both claim the
    same area). Partial (area-limited) coverage beside another zone's whole-district coverage is
    fine — that is exactly how a district gets split.
    """
    cleaned = []
    seen = set()
    for item in items:
        district_id = item["district_id"]
        if district_id in seen:
            raise field_error("coverage", "A district can be listed only once per zone.", "duplicate_district")
        seen.add(district_id)
        areas = list(dict.fromkeys(a.strip() for a in item.get("areas") or [] if a and a.strip()))
        cleaned.append({"district_id": district_id, "areas": areas})

    districts = {d.id: d for d in District.objects.filter(pk__in=seen)}
    for item in cleaned:
        if item["district_id"] not in districts:
            raise field_error("coverage", f"Unknown district id {item['district_id']}.", "unknown_district")

    others = ZoneDistrict.objects.filter(district_id__in=seen).select_related("zone")
    if zone.pk:
        others = others.exclude(zone_id=zone.pk)
    by_district = {}
    for link in others:
        by_district.setdefault(link.district_id, []).append(link)
    for item in cleaned:
        district = districts[item["district_id"]]
        mine = {normalize_name(a) for a in item["areas"]}
        for link in by_district.get(district.id, []):
            theirs = {normalize_name(a) for a in link.areas}
            if not item["areas"] and not link.areas:
                raise field_error(
                    "coverage", f"{district.name} is already covered by the zone “{link.zone.name}”. Remove it there first.",
                    "district_already_assigned",
                )
            if mine & theirs:
                raise field_error(
                    "coverage", f"An area of {district.name} is already covered by the zone “{link.zone.name}”.",
                    "area_already_assigned",
                )
    return cleaned


def _replace_coverage(zone, items):
    zone.coverage.all().delete()
    ZoneDistrict.objects.bulk_create(
        [ZoneDistrict(zone=zone, district_id=i["district_id"], areas=i["areas"]) for i in items]
    )


def delete_zone(zone):
    """Delete a zone unless it is the default or has orders (deactivate those instead)."""
    from apps.catalog.exceptions import Conflict

    with transaction.atomic():
        zone = DeliveryZone.objects.select_for_update().get(pk=zone.pk)
        if zone.is_default:
            raise Conflict(
                "The default zone cannot be deleted. Make another zone the default first.", code="default_zone"
            )
        if has_orders(zone):
            raise Conflict(
                "Orders were placed with this zone. Deactivate it instead of deleting it.", code="zone_in_use"
            )
        zone.delete()
