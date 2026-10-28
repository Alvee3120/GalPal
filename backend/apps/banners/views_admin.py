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
from .models import HeroBanner, HeroSliderConfig, MegaMenuBanner
from .serializers import AdminHeroBannerSerializer, AdminMegaMenuBannerSerializer, AdminSliderConfigSerializer

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
    create=extend_schema(
        tags=["Admin – Hero Banners"], summary="Create a banner",
        description="At most 3 banners in total (active or not): a fourth is 400 `max_banners`. Delete one to add another.",
        responses={201: AdminHeroBannerSerializer, 400: ERR},
    ),
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

    def perform_create(self, serializer):
        services.create_banner(serializer)  # at most services.MAX_BANNERS (3) banners

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


@extend_schema_view(
    list=extend_schema(tags=["Admin – Mega Menu"], summary="List mega menu banners"),
    retrieve=extend_schema(tags=["Admin – Mega Menu"], summary="Get a mega menu banner"),
    create=extend_schema(tags=["Admin – Mega Menu"], summary="Create a mega menu banner", responses={201: AdminMegaMenuBannerSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Mega Menu"], summary="Update a mega menu banner", responses={200: AdminMegaMenuBannerSerializer, 400: ERR}),
    destroy=extend_schema(tags=["Admin – Mega Menu"], summary="Delete a mega menu banner"),
)
class AdminMegaMenuBannerViewSet(viewsets.ModelViewSet):
    """Admin → Mega Menu: the three Shop mega menu images (square_1, square_2, wide), one per slot."""

    serializer_class = AdminMegaMenuBannerSerializer
    permission_classes = [IsAdmin]
    queryset = MegaMenuBanner.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["slot", "is_active"]
    search_fields = ["title"]
    ordering_fields = ["slot", "created_at"]
    ordering = ["slot"]

    def perform_destroy(self, instance):
        image = instance.image
        instance.delete()
        discard_file(image)
