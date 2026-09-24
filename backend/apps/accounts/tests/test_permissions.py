import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.accounts.permissions import (
    CCE_ALLOWED_ADMIN_PREFIXES,
    IsAdmin,
    IsAdminOrCCE,
    IsAdminOrReadOnly,
    IsOwner,
)

from . import route_sweep
from .factories import AddressFactory, AdminFactory, CCEFactory, UserFactory

pytestmark = pytest.mark.django_db

factory = APIRequestFactory()


def request_as(user, method="get"):
    request = getattr(factory, method)("/")
    request.user = user if user is not None else AnonymousUser()
    return request


VIEW = APIView()


# --- the four permission classes ------------------------------------------------------------


@pytest.mark.parametrize(
    "user_factory,expected",
    [(AdminFactory, True), (CCEFactory, False), (UserFactory, False), (None, False)],
)
def test_is_admin(user_factory, expected):
    user = user_factory() if user_factory else None
    assert IsAdmin().has_permission(request_as(user), VIEW) is expected


@pytest.mark.parametrize(
    "user_factory,expected",
    [(AdminFactory, True), (CCEFactory, True), (UserFactory, False), (None, False)],
)
def test_is_admin_or_cce(user_factory, expected):
    user = user_factory() if user_factory else None
    assert IsAdminOrCCE().has_permission(request_as(user), VIEW) is expected


def test_inactive_staff_lose_all_role_permissions():
    for user in (AdminFactory(is_active=False), CCEFactory(is_active=False)):
        assert not IsAdmin().has_permission(request_as(user), VIEW)
        assert not IsAdminOrCCE().has_permission(request_as(user), VIEW)


@pytest.mark.parametrize("method", ["get", "head", "options"])
@pytest.mark.parametrize("user_factory", [AdminFactory, CCEFactory, UserFactory, None])
def test_is_admin_or_read_only_allows_everyone_to_read(method, user_factory):
    user = user_factory() if user_factory else None
    assert IsAdminOrReadOnly().has_permission(request_as(user, method), VIEW)


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
@pytest.mark.parametrize("user_factory,expected", [(AdminFactory, True), (CCEFactory, False), (UserFactory, False), (None, False)])
def test_is_admin_or_read_only_restricts_writes_to_admin(method, user_factory, expected):
    user = user_factory() if user_factory else None
    assert bool(IsAdminOrReadOnly().has_permission(request_as(user, method), VIEW)) is expected


def test_is_owner_object_level():
    owner, other = UserFactory(), UserFactory()
    address = AddressFactory(user=owner)
    permission = IsOwner()
    assert permission.has_object_permission(request_as(owner), VIEW, address)
    assert not permission.has_object_permission(request_as(other), VIEW, address)
    assert not permission.has_object_permission(request_as(AdminFactory()), VIEW, address)  # admin isn't the owner
    assert not permission.has_permission(request_as(None), VIEW)


def test_is_owner_supports_custom_owner_field_and_self():
    user, other = UserFactory(), UserFactory()

    class SelfView(APIView):
        owner_field = "self"

    assert IsOwner().has_object_permission(request_as(user), SelfView(), user)
    assert not IsOwner().has_object_permission(request_as(other), SelfView(), user)

    class Thing:
        created_by = user

    class CustomView(APIView):
        owner_field = "created_by"

    assert IsOwner().has_object_permission(request_as(user), CustomView(), Thing())
    assert not IsOwner().has_object_permission(request_as(other), CustomView(), Thing())
    assert not IsOwner().has_object_permission(request_as(user), APIView(), Thing())  # no `user` attr


# --- route sweep: CCE is locked out of everything except orders -----------------------------


def test_sweep_finds_the_admin_routes():
    routes = route_sweep.admin_routes()
    assert "/api/v1/admin/staff/" in routes and "/api/v1/admin/staff/1/" in routes
    assert "/api/v1/admin/customers/1/activate/" in routes
    assert "/api/v1/admin/site-settings/" in routes  # Module 2 is picked up by the sweep automatically
    for route in ["/api/v1/admin/categories/", "/api/v1/admin/categories/1/", "/api/v1/admin/categories/tree/",
                  "/api/v1/admin/brands/", "/api/v1/admin/brands/1/", "/api/v1/admin/tags/", "/api/v1/admin/tags/1/"]:
        assert route in routes, route  # Module 3
    for route in ["/api/v1/admin/hero-slider-config/", "/api/v1/admin/hero-banners/", "/api/v1/admin/hero-banners/1/", "/api/v1/admin/hero-banners/reorder/"]:
        assert route in routes, route  # Module 5
    for route in ["/api/v1/admin/videos/", "/api/v1/admin/videos/1/", "/api/v1/admin/products/picker/"]:
        assert route in routes, route  # Module 6
    for route in ["/api/v1/admin/coupons/", "/api/v1/admin/coupons/1/", "/api/v1/admin/coupon-usages/", "/api/v1/admin/coupon-usages/1/"]:
        assert route in routes, route  # Module 8
    for route in [
        "/api/v1/admin/products/", "/api/v1/admin/products/1/", "/api/v1/admin/products/1/duplicate/",
        "/api/v1/admin/products/bulk/activate/", "/api/v1/admin/products/bulk/deactivate/", "/api/v1/admin/products/bulk/stock/",
        "/api/v1/admin/products/1/images/", "/api/v1/admin/products/1/images/1/", "/api/v1/admin/products/1/images/reorder/",
        "/api/v1/admin/products/1/variants/", "/api/v1/admin/products/1/variants/1/",
        "/api/v1/admin/product-attributes/", "/api/v1/admin/product-attributes/1/",
        "/api/v1/admin/attribute-values/", "/api/v1/admin/attribute-values/1/",
        "/api/v1/admin/stock-movements/", "/api/v1/admin/stock/adjust/",
    ]:
        assert route in routes, route  # Module 4
    assert not any("<" in r or "(" in r or "^" in r or "$" in r for r in routes), routes
    assert CCE_ALLOWED_ADMIN_PREFIXES == ("/api/v1/admin/orders/",)


def test_anonymous_gets_401_on_every_admin_route(api_client):
    routes = route_sweep.admin_routes()
    bad = [(m, r, s) for m, r, s in route_sweep.probe(api_client, routes) if s != 401]
    assert not bad, bad


def test_customer_gets_403_on_every_admin_route(auth_client, customer):
    routes = route_sweep.admin_routes()
    bad = [(m, r, s) for m, r, s in route_sweep.probe(auth_client(customer), routes) if s != 403]
    assert not bad, bad


def test_cce_gets_403_on_every_admin_route_outside_the_order_module(auth_client, cce_user):
    routes = route_sweep.admin_routes()
    assert route_sweep.cce_violations(auth_client(cce_user), routes) == []


def test_cce_is_let_into_exactly_the_product_management_endpoints(auth_client, cce_user):
    routes = route_sweep.admin_routes()
    assert {r for _, r in route_sweep.CCE_CATALOG_ENDPOINTS} <= set(routes)  # the list names real routes
    client = auth_client(cce_user)
    blocked = [
        (m, r) for m, r in sorted(route_sweep.CCE_CATALOG_ENDPOINTS)
        if getattr(client, m.lower())(r, {}, format="json").status_code in (401, 403)
    ]
    assert blocked == []


def test_inactive_cce_token_is_rejected(auth_client):
    inactive = CCEFactory(is_active=False)
    routes = route_sweep.admin_routes()
    assert {s for _, _, s in route_sweep.probe(auth_client(inactive), routes)} == {401}


def test_admin_is_never_blocked_by_permissions_on_admin_routes(auth_client, admin_user):
    routes = route_sweep.admin_routes()
    blocked = [(m, r, s) for m, r, s in route_sweep.probe(auth_client(admin_user), routes) if s in (401, 403)]
    assert not blocked, blocked


@pytest.mark.urls("apps.accounts.tests.urls_leaky")
def test_the_sweep_really_detects_leaky_routes(auth_client, cce_user):
    """Guard for the guard: a misconfigured URL conf must produce violations."""
    routes = route_sweep.admin_routes()
    assert "/api/v1/admin/orders/" in routes
    leaks = route_sweep.cce_violations(auth_client(cce_user), routes)
    leaked_paths = {r for _, r, _ in leaks}
    assert leaked_paths == {"/api/v1/admin/products/", "/api/v1/admin/reports/"}
    assert "/api/v1/admin/safe/" not in leaked_paths  # correctly protected
    assert "/api/v1/admin/orders/" not in leaked_paths  # allowed for CCE, not a violation
