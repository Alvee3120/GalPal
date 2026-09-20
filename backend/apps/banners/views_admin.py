"""Admin endpoints: slider config and banner CRUD/reorder. Admin only (CCE gets 403)."""

from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin
from apps.core.serializers import ErrorResponseSerializer
from apps.core.utils import discard_file

from . import services
from .models import HeroBanner, HeroSliderConfig
from .serializers import AdminHeroBannerSerializer, AdminSliderConfigSerializer

ERR = OpenApiResponse(ErrorResponseSerializer)


@extend_schema_view(
    get=extend_schema(tags=["Admin – Hero Banners"], summary="Get the slider config"),
    patch=extend_schema(tags=["Admin – Hero Banners"], summary="Update the slider config", responses={200: AdminSliderConfigSerializer, 400: ERR}),
)
class AdminSliderConfigView(generics.RetrieveUpdateAPIView):
    serializer_class = AdminSliderConfigSerializer
    permission_classes = [IsAdmin]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return HeroSliderConfig.objects.get_or_create(id=1)[0]  # always the live row, never the cache


@extend_schema_view(
    list=extend_schema(tags=["Admin – Hero Banners"], summary="List banners (including inactive/expired)"),
    retrieve=extend_schema(tags=["Admin – Hero Banners"], summary="Get a banner"),
    create=extend_schema(tags=["Admin – Hero Banners"], summary="Create a banner", responses={201: AdminHeroBannerSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Hero Banners"], summary="Update a banner", responses={200: AdminHeroBannerSerializer, 400: ERR}),
    destroy=extend_schema(tags=["Admin – Hero Banners"], summary="Delete a banner"),
)
class AdminHeroBannerViewSet(viewsets.ModelViewSet):
    serializer_class = AdminHeroBannerSerializer
    permission_classes = [IsAdmin]
    queryset = HeroBanner.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["is_active"]
    search_fields = ["title"]
    ordering_fields = ["sort_order", "created_at", "start_at", "end_at"]
    ordering = ["sort_order", "-created_at"]

    def perform_destroy(self, instance):
        images = [instance.desktop_image, instance.tablet_image, instance.mobile_image]
        instance.delete()
        for image in images:
            discard_file(image)

    @extend_schema(
        tags=["Admin – Hero Banners"], summary="Reorder banners",
        description="Body: a list of banner ids in the desired order (must be exactly the current set of ids).",
        request={"application/json": {"type": "array", "items": {"type": "integer"}}},
        responses={200: AdminHeroBannerSerializer(many=True), 400: ERR},
    )
    @action(detail=False, methods=["post"])
    def reorder(self, request):
        ids = request.data if isinstance(request.data, list) else request.data.get("order", [])
        try:
            banners = services.reorder_banners(ids)
        except ValueError as exc:
            raise ValidationError(str(exc)) from None
        return Response(AdminHeroBannerSerializer(banners, many=True, context=self.get_serializer_context()).data)
