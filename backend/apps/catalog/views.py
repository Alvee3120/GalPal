"""Public (storefront) read-only endpoints."""

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import services
from .filters import PublicCategoryFilter
from .models import Brand, Category, Tag
from .serializers import (
    PublicBrandSerializer,
    PublicCategoryDetailSerializer,
    PublicCategorySerializer,
    PublicCategoryTreeNodeSerializer,
    PublicTagSerializer,
)


class _PublicReadOnly(viewsets.ReadOnlyModelViewSet):
    authentication_classes = []  # a stale token must not break a public page
    permission_classes = [AllowAny]
    lookup_field = "slug"


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List categories (flat)", description="Only categories that are active and whose ancestors are all active."),
    retrieve=extend_schema(
        tags=["Catalog"], summary="Category by slug",
        description="Includes SEO fields, the breadcrumb (root to this category) and visible sub-categories.",
    ),
)
class PublicCategoryViewSet(_PublicReadOnly):
    filterset_class = PublicCategoryFilter
    search_fields = ["name"]
    ordering_fields = ["sort_order", "name", "created_at"]
    ordering = ["sort_order", "name"]

    @property
    def index(self):
        if not hasattr(self, "_index"):
            self._index = services.CategoryIndex()
        return self._index

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Category.objects.none()
        return Category.objects.filter(pk__in=self.index.visible_ids()).select_related("parent")

    def get_serializer_class(self):
        return PublicCategoryDetailSerializer if self.action == "retrieve" else PublicCategorySerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "index": self.index}

    @extend_schema(
        tags=["Catalog"], summary="Category tree",
        description=(
            "All visible categories nested by `children`, in display order. Not paginated: it is "
            "the whole (small) tree in one response, ready to render a menu."
        ),
        responses=PublicCategoryTreeNodeSerializer(many=True),
    )
    @action(detail=False, pagination_class=None, filter_backends=[])
    def tree(self, request):
        categories = list(
            Category.objects.filter(pk__in=self.index.visible_ids()).select_related("parent").order_by("sort_order", "name")
        )
        serializer = PublicCategorySerializer(context=self.get_serializer_context())
        return Response(services.build_tree(categories, serializer.to_representation))


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List brands (active only)"),
    retrieve=extend_schema(tags=["Catalog"], summary="Brand by slug"),
)
class PublicBrandViewSet(_PublicReadOnly):
    serializer_class = PublicBrandSerializer
    queryset = Brand.objects.filter(is_active=True)
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


@extend_schema_view(
    list=extend_schema(tags=["Catalog"], summary="List tags"),
    retrieve=extend_schema(tags=["Catalog"], summary="Tag by slug"),
)
class PublicTagViewSet(_PublicReadOnly):
    serializer_class = PublicTagSerializer
    queryset = Tag.objects.all()
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]
