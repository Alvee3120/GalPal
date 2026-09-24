"""
Default shipping data: the 64 districts, the two starter zones and the two delivery methods.

Used by the data migration (`0002_seed_defaults`, with *historical* models) and by the
`seed_shipping` command (with the real ones), so both take the model classes as arguments.
Everything is create-if-missing: running it again never overwrites a charge the Admin has edited.
"""
from decimal import Decimal

from django.utils.text import slugify

# division -> [(district, [alternative spellings])]
DISTRICTS = {
    "Dhaka": [
        ("Dhaka", []), ("Faridpur", []), ("Gazipur", []), ("Gopalganj", []), ("Kishoreganj", []),
        ("Madaripur", []), ("Manikganj", []), ("Munshiganj", []), ("Narayanganj", []),
        ("Narsingdi", ["Narsinghdi"]), ("Rajbari", []), ("Shariatpur", []), ("Tangail", []),
    ],
    "Chattogram": [
        ("Bandarban", []), ("Brahmanbaria", ["Brahmanbaria", "B. Baria"]), ("Chandpur", []),
        ("Chattogram", ["Chittagong"]), ("Cox's Bazar", ["Coxs Bazar", "Cox Bazar", "Coxbazar"]),
        ("Cumilla", ["Comilla"]), ("Feni", []), ("Khagrachhari", ["Khagrachari"]),
        ("Lakshmipur", ["Laxmipur", "Lakhipur"]), ("Noakhali", []), ("Rangamati", []),
    ],
    "Rajshahi": [
        ("Bogura", ["Bogra"]), ("Chapainawabganj", ["Chapai Nawabganj", "Nawabganj"]),
        ("Joypurhat", ["Jaipurhat"]), ("Naogaon", []), ("Natore", []), ("Pabna", []),
        ("Rajshahi", []), ("Sirajganj", []),
    ],
    "Khulna": [
        ("Bagerhat", []), ("Chuadanga", []), ("Jashore", ["Jessore"]), ("Jhenaidah", ["Jhenidah"]),
        ("Khulna", []), ("Kushtia", []), ("Magura", []), ("Meherpur", []), ("Narail", []), ("Satkhira", []),
    ],
    "Barishal": [
        ("Barguna", []), ("Barishal", ["Barisal"]), ("Bhola", []), ("Jhalokati", ["Jhalakathi", "Jhalokathi"]),
        ("Patuakhali", []), ("Pirojpur", []),
    ],
    "Sylhet": [
        ("Habiganj", ["Hobiganj"]), ("Moulvibazar", ["Maulvibazar", "Moulvi Bazar"]), ("Sunamganj", []), ("Sylhet", []),
    ],
    "Rangpur": [
        ("Dinajpur", []), ("Gaibandha", []), ("Kurigram", []), ("Lalmonirhat", []), ("Nilphamari", []),
        ("Panchagarh", []), ("Rangpur", []), ("Thakurgaon", []),
    ],
    "Mymensingh": [
        ("Jamalpur", []), ("Mymensingh", []), ("Netrokona", ["Netrakona"]), ("Sherpur", []),
    ],
}

INSIDE_DHAKA = {
    "name": "Inside Dhaka", "slug": "inside-dhaka", "charge": Decimal("70.00"), "sort_order": 1,
    "estimated_days_min": 1, "estimated_days_max": 2,
    "description": "Dhaka district. The Admin can narrow this to specific areas/thanas, e.g. Dhaka city only.",
}
OUTSIDE_DHAKA = {
    "name": "Outside Dhaka", "slug": "outside-dhaka", "charge": Decimal("120.00"), "sort_order": 2,
    "estimated_days_min": 3, "estimated_days_max": 5, "is_default": True,
    "description": "Fallback zone: every district no other zone covers.",
}
# The Dhaka upazilas outside the city (matches the storefront's zone list). Area-limited coverage of Dhaka, so it
# wins over Inside Dhaka's whole-district coverage for these areas only.
DHAKA_OUTER = {
    "name": "Dhaka Outer Zones", "slug": "dhaka-outer-zones", "charge": Decimal("100.00"), "sort_order": 2,
    "estimated_days_min": 1, "estimated_days_max": 3,
    "description": "Dhamrai, Dohar, Keraniganj, Nawabganj and Savar in Dhaka district.",
}
DHAKA_OUTER_AREAS = ["Dhamrai", "Dohar", "Keraniganj", "Nawabganj", "Savar"]
METHODS = [
    {"name": "Standard", "slug": "standard", "extra_charge": Decimal("0.00"), "is_active": True, "sort_order": 1,
     "description": "Regular delivery: the zone charge only."},
    {"name": "Express", "slug": "express", "extra_charge": Decimal("100.00"), "is_active": False, "sort_order": 2,
     "estimated_days_label": "Next day", "description": "Faster delivery for an extra fee. Off until the Admin enables it."},
]


def seed_districts(District):
    created = 0
    for division, rows in DISTRICTS.items():
        for name, aliases in rows:
            _, was_created = District.objects.get_or_create(
                name=name, defaults={"slug": slugify(name), "division": division, "aliases": aliases}
            )
            created += was_created
    return created


def seed_zones(DeliveryZone, ZoneDistrict, District, ShippingChargeHistory=None):
    """Create the two starter zones if they're missing. Returns the names created."""
    created = []
    for spec in (INSIDE_DHAKA, OUTSIDE_DHAKA):
        if DeliveryZone.objects.filter(slug=spec["slug"]).exists():
            continue
        if spec.get("is_default") and DeliveryZone.objects.filter(is_default=True).exists():
            continue  # the Admin already chose a different default; never fight it
        if DeliveryZone.objects.filter(name__iexact=spec["name"]).exists():
            continue
        zone = DeliveryZone.objects.create(**spec)
        created.append(zone.name)
        if ShippingChargeHistory is not None:
            ShippingChargeHistory.objects.create(zone=zone, zone_name=zone.name, old_charge=None, new_charge=zone.charge)
    dhaka = District.objects.filter(name="Dhaka").first()
    inside = DeliveryZone.objects.filter(slug=INSIDE_DHAKA["slug"]).first()
    if dhaka and inside and not ZoneDistrict.objects.filter(district=dhaka).exists():
        ZoneDistrict.objects.create(zone=inside, district=dhaka, areas=[])
    return created


def seed_dhaka_outer_zone(DeliveryZone, ZoneDistrict, District, ShippingChargeHistory=None):
    """
    Create the Dhaka Outer Zones zone if it's missing and no other zone already claims those areas.
    Run by migration 0003 only (not part of seed_all), so existing and fresh databases both get it once.
    """
    dhaka = District.objects.filter(name="Dhaka").first()
    if dhaka is None or DeliveryZone.objects.filter(slug=DHAKA_OUTER["slug"]).exists():
        return []
    if DeliveryZone.objects.filter(name__iexact=DHAKA_OUTER["name"]).exists():
        return []
    wanted = {a.casefold() for a in DHAKA_OUTER_AREAS}
    for link in ZoneDistrict.objects.filter(district=dhaka).exclude(areas=[]):
        if wanted & {a.casefold() for a in link.areas}:
            return []  # the Admin already split Dhaka their own way; never fight it
    zone = DeliveryZone.objects.create(**DHAKA_OUTER)
    ZoneDistrict.objects.create(zone=zone, district=dhaka, areas=DHAKA_OUTER_AREAS)
    if ShippingChargeHistory is not None:
        ShippingChargeHistory.objects.create(zone=zone, zone_name=zone.name, old_charge=None, new_charge=zone.charge)
    return [zone.name]


def seed_methods(DeliveryMethod):
    created = []
    for spec in METHODS:
        _, was_created = DeliveryMethod.objects.get_or_create(slug=spec["slug"], defaults=spec)
        if was_created:
            created.append(spec["name"])
    return created


def seed_all(District, DeliveryZone, ZoneDistrict, DeliveryMethod, ShippingChargeHistory=None):
    return {
        "districts": seed_districts(District),
        "zones": seed_zones(DeliveryZone, ZoneDistrict, District, ShippingChargeHistory),
        "methods": seed_methods(DeliveryMethod),
    }
