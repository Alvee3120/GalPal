"""Helpers that enumerate every /api/v1/admin/ route and probe it as each role."""
import re

from django.urls import URLPattern, URLResolver, get_resolver

from apps.accounts.permissions import CCE_ALLOWED_ADMIN_PREFIXES

ADMIN_PREFIX = "/api/v1/admin/"
METHODS = ["get", "post", "put", "patch", "delete"]


def _segment(pattern):
    text = str(pattern)
    text = re.sub(r"\(\?P<\w+>[^)]*\)", "1", text)  # regex named group -> 1
    text = re.sub(r"<[^>]+>", "1", text)  # path converter -> 1
    return text.lstrip("^").rstrip("$")


def _walk(patterns, prefix=""):
    for entry in patterns:
        if isinstance(entry, URLResolver):
            yield from _walk(entry.url_patterns, prefix + _segment(entry.pattern))
        elif isinstance(entry, URLPattern):
            yield prefix + _segment(entry.pattern)


def admin_routes():
    """Concrete URLs (path params replaced with `1`) of every admin route."""
    routes = sorted({"/" + path for path in _walk(get_resolver().url_patterns)})
    return [route for route in routes if route.startswith(ADMIN_PREFIX)]


# Product management (apps.accounts.permissions.IsCatalogStaff): the exact (method, route) pairs a CCE may use
# outside the order module. Everything else under /api/v1/admin/ must still be 403 for CCE.
_A = ADMIN_PREFIX
CCE_CATALOG_ENDPOINTS = frozenset({
    ("GET", f"{_A}products/"), ("POST", f"{_A}products/"),
    ("GET", f"{_A}products/1/"), ("PATCH", f"{_A}products/1/"), ("DELETE", f"{_A}products/1/"),
    ("GET", f"{_A}products/1/images/"), ("POST", f"{_A}products/1/images/"), ("POST", f"{_A}products/1/images/reorder/"),
    ("GET", f"{_A}products/1/images/1/"), ("PATCH", f"{_A}products/1/images/1/"), ("DELETE", f"{_A}products/1/images/1/"),
    ("GET", f"{_A}products/1/variants/"), ("POST", f"{_A}products/1/variants/"),
    ("GET", f"{_A}products/1/variants/1/"), ("PATCH", f"{_A}products/1/variants/1/"), ("DELETE", f"{_A}products/1/variants/1/"),
    ("POST", f"{_A}stock/adjust/"), ("GET", f"{_A}stock-notifications/"), ("PATCH", f"{_A}stock-notifications/1/"),
    ("GET", f"{_A}categories/"), ("POST", f"{_A}categories/"), ("GET", f"{_A}categories/tree/"),
    ("GET", f"{_A}categories/1/"), ("PATCH", f"{_A}categories/1/"), ("DELETE", f"{_A}categories/1/"),
    ("GET", f"{_A}brands/"), ("POST", f"{_A}brands/"),
    ("GET", f"{_A}brands/1/"), ("PATCH", f"{_A}brands/1/"), ("DELETE", f"{_A}brands/1/"),
    ("GET", f"{_A}tags/"), ("POST", f"{_A}tags/"), ("GET", f"{_A}tags/1/"),
    ("GET", f"{_A}product-attributes/"), ("GET", f"{_A}product-attributes/1/"),
    ("GET", f"{_A}reviews/"), ("GET", f"{_A}reviews/1/"), ("DELETE", f"{_A}reviews/1/"),
    ("POST", f"{_A}reviews/1/approve/"), ("POST", f"{_A}reviews/1/reject/"),
    ("GET", f"{_A}attribute-values/"), ("POST", f"{_A}attribute-values/"), ("GET", f"{_A}attribute-values/1/"),
})


def cce_may_access(route):
    return route.startswith(CCE_ALLOWED_ADMIN_PREFIXES)


def probe(client, routes):
    """[(method, route, status)] for every method on every route."""
    return [(m.upper(), r, getattr(client, m)(r, {}, format="json").status_code) for r in routes for m in METHODS]


def cce_violations(cce_client, routes):
    """Non-order admin routes where CCE did NOT get 403, other than the product-management endpoints."""
    return [
        (m, r, s) for m, r, s in probe(cce_client, [r for r in routes if not cce_may_access(r)])
        if s != 403 and (m, r) not in CCE_CATALOG_ENDPOINTS
    ]
