"""
Keeps the current request reachable for `services.record` (actor + IP for event entries), and writes one request
entry for every write (POST/PUT/PATCH/DELETE) under /api/v1/admin/ made by an Admin or CCE — allowed or refused.
"""

from . import services

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ADMIN_PREFIX = "/api/v1/admin/"
MAX_JSON_BYTES = 256 * 1024


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        audited = request.method in WRITE_METHODS and request.path.startswith(ADMIN_PREFIX)
        if audited and request.META.get("CONTENT_TYPE", "").startswith("application/json"):
            try:
                if int(request.META.get("CONTENT_LENGTH") or 0) <= MAX_JSON_BYTES:
                    request._audit_body = request.body  # read once; Django caches it, so DRF can still parse it
            except Exception:  # noqa: BLE001
                request._audit_body = b""
        token = services.set_request(request)
        try:
            response = self.get_response(request)
        finally:
            services.reset_request(token)
        if audited:
            user = getattr(request, "user", None)  # DRF copies the JWT-authenticated user onto the Django request
            if user is not None and user.is_authenticated and getattr(user, "role", "") in services.STAFF_ROLES:
                entry = services.record(
                    f"api.{request.method.lower()}", actor=user, request=request,
                    metadata={"body": services.request_body(request)},
                )
                if entry is not None:
                    entry.method, entry.path, entry.status_code = request.method, request.path[:300], response.status_code
                    entry.save(update_fields=["method", "path", "status_code"])
        return response
