"""Admin endpoint: video card CRUD. Admin only (CCE gets 403)."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import viewsets

from apps.accounts.permissions import CatalogStaffActionsMixin, IsAdmin
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .models import VideoCard
from .serializers import AdminVideoCardSerializer

ERR = OpenApiResponse(ErrorResponseSerializer)


@extend_schema_view(
    list=extend_schema(tags=["Admin – Video Cards"], summary="List video cards (including inactive)"),
    retrieve=extend_schema(tags=["Admin – Video Cards"], summary="Get a video card"),
    create=extend_schema(
        tags=["Admin – Video Cards"], summary="Create a video card",
        description="Provide exactly one of `video_file` (mp4/webm) or `external_url` (e.g. a YouTube link).",
        responses={201: AdminVideoCardSerializer, 400: ERR},
    ),
    partial_update=extend_schema(tags=["Admin – Video Cards"], summary="Update a video card", responses={200: AdminVideoCardSerializer, 400: ERR}),
    destroy=extend_schema(tags=["Admin – Video Cards"], summary="Delete a video card"),
)
class AdminVideoCardViewSet(CatalogStaffActionsMixin, viewsets.ModelViewSet):
    serializer_class = AdminVideoCardSerializer
    permission_classes = [IsAdmin]
    # Video Card Management is shared by Admin and CCE (IsCatalogStaff); the product picker stays Admin only.
    cce_actions = frozenset({"list", "retrieve", "create", "partial_update", "destroy"})
    queryset = VideoCard.objects.prefetch_related("products")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["is_active"]
    search_fields = ["title"]
    ordering_fields = ["sort_order", "created_at"]
    ordering = ["sort_order", "-created_at"]

    def perform_destroy(self, instance):
        services.delete_video(instance)
