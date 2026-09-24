"""Admin endpoints (Admin only; CCE gets 403 except the actions each viewset lists in `cce_actions`)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import CatalogStaffActionsMixin, IsAdmin
from apps.core.serializers import ErrorResponseSerializer
from apps.core.utils import discard_file

from . import services
from .filters import AdminBrandFilter, AdminCategoryFilter, AdminTagFilter
from .models import Brand, Category, Tag
from .serializers import (
    AdminBrandSerializer,
    AdminCategorySerializer,
    AdminCategoryTreeNodeSerializer,
    AdminTagSerializer,
)

ERR = OpenApiResponse(ErrorResponseSerializer)


class _AdminModelViewSet(CatalogStaffActionsMixin, viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]


@extend_schema_view(
    list=extend_schema(tags=["Admin – Categories"], summary="List categories (including inactive)"),
    retrieve=extend_schema(tags=["Admin – Categories"], summary="Get a category"),
    create=extend_schema(tags=["Admin – Categories"], summary="Create a category", responses={201: AdminCategorySerializer, 400: ERR}),
    partial_update=extend_schema(
        tags=["Admin – Categories"], summary="Update a category",
        description="Changing `parent` is rejected if it would create a loop (400 on `parent`). "
        "Renaming regenerates the slug unless you set it by hand.",
        responses={200: AdminCategorySerializer, 400: ERR},
    ),
    destroy=extend_schema(
        tags=["Admin – Categories"], summary="Delete a category",
        description=(
            "Refused with **409** if the category has products (`category_has_products`) or sub-categories "
            "(`category_has_children`). Pass `move_children_to` to re-parent the sub-categories and delete anyway. "
            "Products always block deletion: deactivate the category instead."
        ),
        parameters=[OpenApiParameter("move_children_to", str, description="`root` or a category id to receive the sub-categories")],
        responses={204: None, 400: ERR, 409: OpenApiResponse(ErrorResponseSerializer, description="Category in use")},
    ),
)
class AdminCategoryViewSet(_AdminModelViewSet):
    # Category Management in the CCE dashboard, plus the product form's category picker. Same serializer and
    # services as Admin, so the same rules hold (no loops, and deleting is refused while products/children depend on it).
    cce_actions = frozenset({"list", "retrieve", "tree", "create", "partial_update", "destroy"})
    serializer_class = AdminCategorySerializer
    filterset_class = AdminCategoryFilter
    search_fields = ["name", "slug"]
    ordering_fields = ["sort_order", "name", "created_at", "updated_at"]
    ordering = ["sort_order", "name"]

    def get_queryset(self):
        return Category.objects.select_related("parent").annotate(
            children_count=Count("children", distinct=True), products_count=Count("products", distinct=True)
        )

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        target = request.query_params.get("move_children_to")
        if target is not None and target != services.ROOT:
            if not target.isdigit():
                raise ValidationError({"move_children_to": ["Use 'root' or a category id."]})
            target = int(target)
        try:
            services.delete_category(category, move_children_to=target)
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict) from None
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Admin – Categories"], summary="Category tree (including inactive)",
        description="Every category nested by `children`, for parent pickers and the category manager. Not paginated.",
        responses=AdminCategoryTreeNodeSerializer(many=True),
    )
    @action(detail=False, pagination_class=None, filter_backends=[])
    def tree(self, request):
        categories = list(Category.objects.select_related("parent").order_by("sort_order", "name"))
        serializer = AdminCategoryTreeNodeSerializer(context=self.get_serializer_context())
        return Response(services.build_tree(categories, serializer.to_representation))


@extend_schema_view(
    list=extend_schema(tags=["Admin – Brands"], summary="List brands (including inactive)"),
    retrieve=extend_schema(tags=["Admin – Brands"], summary="Get a brand"),
    create=extend_schema(tags=["Admin – Brands"], summary="Create a brand", responses={201: AdminBrandSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Brands"], summary="Update a brand", responses={200: AdminBrandSerializer, 400: ERR}),
    destroy=extend_schema(tags=["Admin – Brands"], summary="Delete a brand"),
)
class AdminBrandViewSet(_AdminModelViewSet):
    # Brand Management in the CCE dashboard, plus the product form's brand picker. Same serializer as Admin;
    # deleting a brand leaves its products brandless (Product.brand is SET_NULL), exactly as for Admin.
    cce_actions = frozenset({"list", "retrieve", "create", "partial_update", "destroy"})
    serializer_class = AdminBrandSerializer
    queryset = Brand.objects.all()
    filterset_class = AdminBrandFilter
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def perform_destroy(self, instance):
        logo = instance.logo
        instance.delete()
        discard_file(logo)


@extend_schema_view(
    list=extend_schema(tags=["Admin – Tags"], summary="List tags"),
    retrieve=extend_schema(tags=["Admin – Tags"], summary="Get a tag"),
    create=extend_schema(tags=["Admin – Tags"], summary="Create a tag", responses={201: AdminTagSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Tags"], summary="Update a tag", responses={200: AdminTagSerializer, 400: ERR}),
    destroy=extend_schema(tags=["Admin – Tags"], summary="Delete a tag"),
)
class AdminTagViewSet(_AdminModelViewSet):
    cce_actions = frozenset({"list", "retrieve", "create"})  # the product form's tag picker, incl. "+ Add Tag"
    serializer_class = AdminTagSerializer
    queryset = Tag.objects.all()
    filterset_class = AdminTagFilter
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]
