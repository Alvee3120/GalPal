"""
Extra security headers for API responses (Module 18), on top of Django's SecurityMiddleware (HSTS, nosniff,
referrer policy, X-Frame-Options, COOP).

* JSON/CSV API responses get a CSP that allows nothing at all (`default-src 'none'`): an API response is never
  meant to render as a page, so even a reflected value can't run there. The Swagger/ReDoc pages and Django's admin
  are left alone (they need their own scripts and styles).
* `Permissions-Policy` turns off powerful browser features for everything served from the API host.
* Admin/CCE and account responses are `Cache-Control: no-store`, so personal data is never kept by a proxy or the
  browser's back-forward cache.
"""

SKIP_CSP = ("/api/docs", "/api/redoc", "/django-admin", "/static/", "/media/")
NO_STORE = ("/api/v1/admin/", "/api/v1/auth/", "/api/v1/account/", "/api/v1/orders/")
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        if not path.startswith(SKIP_CSP):
            response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if path.startswith(NO_STORE):
            response.headers["Cache-Control"] = "no-store"
        return response
