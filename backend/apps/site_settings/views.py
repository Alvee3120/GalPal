from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.accounts.permissions import IsAdmin
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .models import SiteSettings
from .serializers import AdminSiteSettingsSerializer, PublicSiteSettingsSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["Site Settings"],
        summary="Public site settings (safe subset)",
        description=(
            "Branding, contact, social links, public tracking IDs and scripts, and commerce flags. "
            "Never includes secrets (Meta CAPI token, GA4 API secret) or internal flags. Served from cache."
        ),
        auth=[],
    )
)
class PublicSiteSettingsView(generics.RetrieveAPIView):
    serializer_class = PublicSiteSettingsSerializer
    authentication_classes = []  # a stale token must not break a public page
    permission_classes = [AllowAny]

    def get_object(self):
        return services.get_site_settings()


@extend_schema_view(
    get=extend_schema(
        tags=["Admin – Site Settings"],
        summary="All site settings (secrets masked)",
        responses={200: AdminSiteSettingsSerializer, 403: OpenApiResponse(ErrorResponseSerializer)},
    ),
    patch=extend_schema(
        tags=["Admin – Site Settings"],
        summary="Update site settings",
        description=(
            "Partial update; send only the fields to change. Use `multipart/form-data` to upload "
            "`logo`, `favicon` or `default_og_image` (send an empty value to remove one).\n\n"
            "Secret fields come back masked; sending the masked value back leaves the secret unchanged, "
            "a new value replaces it, and an empty string clears it. Changes apply immediately."
        ),
        responses={
            200: AdminSiteSettingsSerializer,
            400: OpenApiResponse(ErrorResponseSerializer, description="Validation error"),
            403: OpenApiResponse(ErrorResponseSerializer),
        },
    ),
)
class AdminSiteSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class = AdminSiteSettingsSerializer
    permission_classes = [IsAdmin]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        # Always the live row, not the cached copy: the admin form must never show stale data.
        return SiteSettings.objects.get_or_create(id=1)[0]
