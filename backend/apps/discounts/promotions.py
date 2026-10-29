"""
Cart-level promotions: the offers that depend on how many eligible units are in the cart, not on a single product's
price (Buy X Get Y% off, Buy X Get Y free, lowest-priced item free, 3 for 2, fixed bundle price).

The ONE engine the whole backend shares: `apps.cart.services.summarize` (cart page / drawer), `apps.orders.services`
(checkout, order snapshot) and the invoice all work out promotions through `apply_promotions`, so a customer is shown
exactly what they are charged. The frontend never computes a promotion itself.

RULES (deterministic, never stacked on the same units):
1. Only live rules of the cart kinds count (switched on, inside their start/end window — evaluated against *now*).
2. Rules run in priority order: product-targeted before category-targeted, then `priority`, then id. A unit consumed by
   one rule is never offered to another, so the same unit can't collect two free-item / bundle offers.
3. Units are grouped by their effective unit price, ascending; the group is the cheapest complete set available.
4. A complete group gets the offer; a leftover incomplete group never does. `allow_repeat` decides whether the offer
   repeats for every complete group or applies once (to the single most valuable group).
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from . import services
from .models import CART_KINDS, DiscountKind, DiscountTarget, promotion_label

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def _round(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class LineIn:
    """One cart/order line offered to the engine. `unit_price` is the effective price before any promotion."""

    key: tuple  # (product_id, variant_id or None) — maps the result back to the cart line / order item
    product_id: int
    unit_price: Decimal
    quantity: int


@dataclass
class AppliedPromotion:
    id: int
    name: str
    kind: str
    label: str
    discount: Decimal
    groups: int
    free_quantity: int
    allocations: dict = field(default_factory=dict)  # key -> Decimal (this rule's share on that line)
    free_by_line: dict = field(default_factory=dict)  # key -> int (free units this rule grants that line)

    def as_dict(self):
        """JSON-safe snapshot of this promotion for the order (Order.applied_promotions)."""
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "label": self.label,
            "discount": str(self.discount),
            "groups": self.groups,
            "free_quantity": self.free_quantity,
        }


@dataclass
class PromotionResult:
    total: Decimal = Decimal("0.00")
    applied: list = field(default_factory=list)
    by_line: dict = field(default_factory=dict)  # key -> {"promotion_discount": Decimal, "free_quantity": int, "labels": [str]}

    def line(self, key):
        return self.by_line.setdefault(key, {"promotion_discount": Decimal("0.00"), "free_quantity": 0, "labels": []})


# --- grouping -------------------------------------------------------------------------------------------------------


def _group_shape(rule):
    """(group size, how many of the group's cheapest units are free) for a rule."""
    kind = rule.kind
    if kind == DiscountKind.BUY_X_GET_Y_PERCENT:
        return rule.min_quantity, 0
    if kind == DiscountKind.BUY_X_GET_Y_FREE:
        return (rule.min_quantity or 0) + (rule.free_quantity or 0), rule.free_quantity or 0
    if kind == DiscountKind.LOWEST_FREE:
        return rule.min_quantity, 1
    if kind == DiscountKind.THREE_FOR_TWO:
        return 3, 1
    if kind == DiscountKind.BUNDLE_PRICE:
        return rule.min_quantity, 0
    return 0, 0


def _unit_sort_key(unit):
    line = unit["line"]
    return (unit["price"], line.product_id, line.key[1] or 0, unit["li"], unit["i"])


def _partition(rule, eligible):
    """Eligible units, ascending by price; split per product when the free item must be the same product."""
    ordered = sorted(eligible, key=_unit_sort_key)
    if not rule.same_product_group:
        return [ordered]
    by_product = {}
    for unit in ordered:
        by_product.setdefault(unit["line"].product_id, []).append(unit)
    return list(by_product.values())


def _candidate_groups(parts, size):
    if size <= 0:
        return
    for part in parts:
        for start in range(0, len(part) - size + 1, size):
            yield part[start : start + size]


def _group_benefit(rule, group):
    """`(shares, free_units, discount)` for one complete group (sorted ascending). `shares` is `[(unit, Decimal)]`."""
    kind = rule.kind
    if kind == DiscountKind.BUY_X_GET_Y_PERCENT:
        pct = rule.percent_off or Decimal("0")
        shares = [(unit, _round(unit["price"] * pct / HUNDRED)) for unit in group]
        return shares, [], sum((share for _, share in shares), Decimal("0.00"))

    if kind in (DiscountKind.BUY_X_GET_Y_FREE, DiscountKind.LOWEST_FREE, DiscountKind.THREE_FOR_TWO):
        _, free_n = _group_shape(rule)
        free_units = group[:free_n]  # ascending -> the cheapest do not get paid
        shares = [(unit, unit["price"]) for unit in free_units]
        return shares, free_units, sum((share for _, share in shares), Decimal("0.00"))

    if kind == DiscountKind.BUNDLE_PRICE:
        subtotal = sum((unit["price"] for unit in group), Decimal("0.00"))
        discount = subtotal - (rule.bundle_price or Decimal("0"))
        if discount <= 0:
            return [], [], Decimal("0.00")  # never raise the price above what the items already cost
        # spread the discount over the group proportionally to each unit's price; the priciest unit absorbs rounding
        shares, assigned = [], Decimal("0.00")
        for unit in group:
            share = _round(discount * unit["price"] / subtotal)
            shares.append((unit, share))
            assigned += share
        remainder = discount - assigned
        if remainder:
            last_unit, last_share = shares[-1]
            shares[-1] = (last_unit, last_share + remainder)
        return shares, [], discount

    return [], [], Decimal("0.00")


def _apply_rule(rule, eligible):
    size, _ = _group_shape(rule)
    if size <= 0:
        return None
    groups = list(_candidate_groups(_partition(rule, eligible), size))
    if not groups:
        return None

    scored = [(_group_benefit(rule, group)[2], index, group) for index, group in enumerate(groups)]
    if rule.allow_repeat:
        chosen = [item[2] for item in scored]
    else:
        chosen = [max(scored, key=lambda item: (item[0], -item[1]))[2]]  # most valuable group; tie -> earliest

    applied = AppliedPromotion(
        id=rule.id, name=rule.name, kind=rule.kind, label=promotion_label(rule),
        discount=Decimal("0.00"), groups=0, free_quantity=0,
    )
    for group in chosen:
        shares, free_units, discount = _group_benefit(rule, group)
        applied.groups += 1
        for unit in group:
            unit["consumed"] = True
        for unit, share in shares:
            if share:
                key = unit["line"].key
                applied.allocations[key] = applied.allocations.get(key, Decimal("0.00")) + share
                applied.discount += share
        for unit in free_units:
            key = unit["line"].key
            applied.free_by_line[key] = applied.free_by_line.get(key, 0) + 1
            applied.free_quantity += 1
    return applied


# --- public ---------------------------------------------------------------------------------------------------------


def apply_promotions(lines, now=None):
    """
    Work out every live cart promotion for these lines and where each discount lands. Pure of side effects; safe to call
    as often as the cart is read. `lines` are `LineIn` rows whose `unit_price` is the effective price before promotions.
    """
    now = now or timezone.now()
    lines = [line for line in lines if line.quantity > 0 and line.unit_price and line.unit_price > 0]
    result = PromotionResult()
    if not lines:
        return result

    rules = [rule for rule in services.live_rules(now) if rule.kind in CART_KINDS]
    rules.sort(key=lambda rule: (0 if rule.target_type == DiscountTarget.PRODUCTS else 1, rule.priority, rule.id))

    units = []
    for li, line in enumerate(lines):
        for i in range(line.quantity):
            units.append({"line": line, "price": line.unit_price, "li": li, "i": i, "consumed": False})

    for rule in rules:
        eligible = [unit for unit in units if not unit["consumed"] and unit["line"].product_id in rule.product_ids]
        if not eligible:
            continue
        applied = _apply_rule(rule, eligible)
        if applied is None:
            continue
        result.applied.append(applied)

    for applied in result.applied:
        for key, amount in applied.allocations.items():
            line = result.line(key)
            line["promotion_discount"] += amount
            if applied.label not in line["labels"]:
                line["labels"].append(applied.label)
        for key, count in applied.free_by_line.items():
            line = result.line(key)
            line["free_quantity"] += count
            if applied.label not in line["labels"]:
                line["labels"].append(applied.label)

    result.total = sum((applied.discount for applied in result.applied), Decimal("0.00"))
    # Safety net: never discount more than the lines are worth.
    ceiling = sum((line.unit_price * line.quantity for line in lines), Decimal("0.00"))
    if result.total > ceiling:
        result.total = ceiling
    return result
