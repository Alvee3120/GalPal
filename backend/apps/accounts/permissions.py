"""
Role permissions: the single place where the access matrix from the spec lives.

| Area                                             | Admin | CCE                    | Customer   | Guest              |
|--------------------------------------------------|-------|------------------------|------------|--------------------|
| Settings, users/staff, catalog, banners, videos, |       |                        |            |                    |
| coupons, shipping zones, payments, reviews,      | full  | NO (403)               | see below  | see below          |
| customers/care tools, reports                    |       |                        |            |                    |
| Orders (admin API)                               | full  | create manual, view,   | own orders | checkout + track   |
|                                                  |       | change status, notes,  |            |                    |
|                                                  |       | edit while pending     |            |                    |
| Order-scoped helpers (/admin/orders/helpers/)    | yes   | yes (read-only)        | no         | no                 |
| Product management (products, their gallery     | full  | list, view, create,    | no         | no                 |
| images and variants, stock adjust; categories;   |       | edit, delete products, |            |                    |
| brands; attributes read-only; tags and attribute |       | categories and brands; |            |                    |
| values list+create; Notify Me requests (status)) |       | no bulk/duplicate      |            |                    |

Use:
    IsAdmin           every admin-panel endpoint
    IsAdminOrCCE      ONLY endpoints under /api/v1/admin/orders/
    IsCatalogStaff    ONLY the product-management actions listed above, chosen per action by the catalog
                      views (`cce_actions`); every other catalog action stays IsAdmin
    IsAdminOrReadOnly public catalog-style reads, admin writes
    IsOwner           object-level: the object belongs to request.user
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import User

ADMIN_ROLES = frozenset({User.Role.ADMIN})
# Roles allowed into the order module. Nothing else may use these.
ORDER_STAFF_ROLES = frozenset({User.Role.ADMIN, User.Role.CCE})

# Roles allowed into product management (the per-action subset of the catalog admin API above).
CATALOG_STAFF_ROLES = frozenset({User.Role.ADMIN, User.Role.CCE})

# URL prefix (under /api/v1/admin/) that CCE may reach in full; the route-sweep test enforces it, plus the
# individual product-management endpoints it lists in `route_sweep.CCE_CATALOG_ENDPOINTS`.
CCE_ALLOWED_ADMIN_PREFIXES = ("/api/v1/admin/orders/",)


def _has_role(request, roles):
    user = request.user
    return bool(user and user.is_authenticated and user.is_active and user.role in roles)


class IsAdmin(BasePermission):
    message = "Only administrators can perform this action."

    def has_permission(self, request, view):
        return _has_role(request, ADMIN_ROLES)


class IsAdminOrCCE(BasePermission):
    """Order module only (Admin + Customer Care Executive)."""

    message = "Only administrators and customer care executives can perform this action."

    def has_permission(self, request, view):
        return _has_role(request, ORDER_STAFF_ROLES)


class IsCatalogStaff(BasePermission):
    """Product management only (Admin + Customer Care Executive), on the actions a catalog view opts in."""

    message = "Only administrators and customer care executives can perform this action."

    def has_permission(self, request, view):
        return _has_role(request, CATALOG_STAFF_ROLES)


class CatalogStaffActionsMixin:
    """
    For an admin-only catalog viewset: the actions named in `cce_actions` also admit CCE (IsCatalogStaff),
    everything else keeps the view's own permission_classes (IsAdmin). An unmapped method has no action,
    so it never matches and stays admin-only.
    """

    cce_actions = frozenset()

    def get_permissions(self):
        if getattr(self, "action", None) in self.cce_actions:
            return [IsCatalogStaff()]
        return super().get_permissions()


class IsAdminOrReadOnly(BasePermission):
    """Anyone may read (including guests); only Admin may write."""

    message = "Only administrators can modify this resource."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or _has_role(request, ADMIN_ROLES)


class IsOwner(BasePermission):
    """
    Object-level: the object must belong to the requesting user.

    The owner attribute defaults to `user`; override with `owner_field` on the view
    (`"self"` means the object is the user itself).
    """

    message = "You do not have permission to access this resource."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        field = getattr(view, "owner_field", "user")
        owner = obj if field == "self" else getattr(obj, field, None)
        return owner is not None and owner == request.user
