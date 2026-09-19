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


def cce_may_access(route):
    return route.startswith(CCE_ALLOWED_ADMIN_PREFIXES)


def probe(client, routes):
    """[(method, route, status)] for every method on every route."""
    return [(m.upper(), r, getattr(client, m)(r, {}, format="json").status_code) for r in routes for m in METHODS]


def cce_violations(cce_client, routes):
    """Non-order admin routes where CCE did NOT get 403."""
    return [
        (m, r, s) for m, r, s in probe(cce_client, [r for r in routes if not cce_may_access(r)]) if s != 403
    ]
