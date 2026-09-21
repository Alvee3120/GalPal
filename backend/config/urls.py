"""
Root URL configuration.

    /api/v1/            storefront (public + customer) endpoints
    /api/v1/admin/      admin / CCE panel endpoints
    /api/docs/          Swagger UI  (also /api/redoc/, /api/schema/)
    /django-admin/      Django's built-in admin, kept only as a fallback
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("django-admin/", admin.site.urls),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Versioned API. Each module adds its own include here.
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/admin/", include("apps.accounts.urls_admin")),  # before the storefront includes
    path("api/v1/admin/", include("apps.site_settings.urls_admin")),
    path("api/v1/admin/", include("apps.catalog.urls_admin")),
    path("api/v1/admin/", include("apps.banners.urls_admin")),
    path("api/v1/admin/", include("apps.videos.urls_admin")),
    path("api/v1/admin/", include("apps.coupons.urls_admin")),
    path("api/v1/admin/", include("apps.shipping.urls_admin")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.site_settings.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.banners.urls")),
    path("api/v1/", include("apps.videos.urls")),
    path("api/v1/", include("apps.cart.urls")),
    path("api/v1/", include("apps.coupons.urls")),
    path("api/v1/", include("apps.shipping.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# JSON error responses for URLs that never reach DRF (unknown routes, etc.)
handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
