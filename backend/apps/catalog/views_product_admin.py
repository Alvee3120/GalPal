"""Admin endpoints for products, variants, gallery images, attributes and inventory.

Admin only (CCE gets 403), except the lightweight product picker which Module 10 will also
grant to CCE for building manual orders.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.core.serializers import ErrorResponseSerializer
from apps.core.utils import discard_file

from . import services
from .filters_product import AdminProductFilter, annotate_effective_price
from .models import AttributeValue, Product, ProductAttribute, ProductImage, ProductVariant, StockMovement
from .serializers_product import (
    AdminAttributeValueSerializer,
    AdminProductAttributeSerializer,
    AdminProductImageSerializer,
    AdminProductListSerializer,
    AdminProductSerializer,
    AdminVariantSerializer,
    BulkIdsSerializer,
    BulkStockUpdateSerializer,
    ProductPickerSerializer,
    StockAdjustmentSerializer,
    StockMovementSerializer,
)

ERR = OpenApiResponse(ErrorResponseSerializer)


def _raise(exc):
    raise ValidationError(exc.message_dict) from None


# --- products --------------------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(tags=["Admin – Products"], summary="List products (compact shape, all statuses)"),
    retrieve=extend_schema(tags=["Admin – Products"], summary="Get a product (full detail)"),
    create=extend_schema(tags=["Admin – Products"], summary="Create a product", responses={201: AdminProductSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Products"], summary="Update a product", responses={200: AdminProductSerializer, 400: ERR}),
    destroy=extend_schema(tags=["Admin – Products"], summary="Delete a product (soft delete)"),
)
class AdminProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_class = AdminProductFilter
    search_fields = ["name", "sku", "barcode", "brand__name"]
    ordering_fields = ["created_at", "updated_at", "name", "regular_price", "stock_quantity"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Product.objects.select_related("brand").prefetch_related(
            "category_links__category", "tags", "images", "variants__attribute_values__attribute"
        )
        return annotate_effective_price(queryset)

    def get_serializer_class(self):
        return AdminProductListSerializer if self.action == "list" else AdminProductSerializer

    @extend_schema(
        tags=["Admin – Products"], summary="Duplicate a product",
        description="Deep-copies the product (categories, tags, gallery, variants) as a new draft with a fresh SKU and zero stock.",
        request=None, responses={201: AdminProductSerializer},
    )
    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        copy = services.duplicate_product(self.get_object())
        return Response(AdminProductSerializer(copy, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Admin – Products"], summary="Bulk activate (publish) products",
        request=BulkIdsSerializer, responses={200: OpenApiResponse(description="`{\"updated\": <count>}`")},
    )
    @action(detail=False, methods=["post"], url_path="bulk/activate")
    def bulk_activate(self, request):
        return self._bulk_status(request, "published")

    @extend_schema(
        tags=["Admin – Products"], summary="Bulk deactivate (draft) products",
        request=BulkIdsSerializer, responses={200: OpenApiResponse(description="`{\"updated\": <count>}`")},
    )
    @action(detail=False, methods=["post"], url_path="bulk/deactivate")
    def bulk_deactivate(self, request):
        return self._bulk_status(request, "draft")

    def _bulk_status(self, request, status_value):
        serializer = BulkIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.bulk_set_status(serializer.validated_data["product_ids"], status_value)
        return Response({"updated": updated})

    @extend_schema(
        tags=["Admin – Products"], summary="Bulk stock update",
        description="Applies each adjustment atomically (all-or-nothing) and logs one StockMovement per item.",
        request=BulkStockUpdateSerializer,
        responses={200: OpenApiResponse(StockMovementSerializer(many=True)), 400: ERR},
    )
    @action(detail=False, methods=["post"], url_path="bulk/stock")
    def bulk_stock(self, request):
        serializer = BulkStockUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        movements = []
        errors = []
        # One outer transaction: adjust_stock's own @transaction.atomic becomes a savepoint per
        # item, so raising after the loop rolls back every item, not just the one that failed.
        with transaction.atomic():
            for index, item in enumerate(serializer.validated_data["items"]):
                try:
                    movements.append(_apply_stock_adjustment(item, request.user))
                except DjangoValidationError as exc:
                    errors.append({"index": index, **exc.message_dict})
            if errors:
                raise ValidationError({"items": errors})
        return Response(StockMovementSerializer(movements, many=True).data)


def _apply_stock_adjustment(item, user):
    product = variant = None
    if item.get("product_id"):
        try:
            product = Product.objects.get(pk=item["product_id"])
        except Product.DoesNotExist:
            raise DjangoValidationError({"product_id": ["Product not found."]}) from None
    else:
        try:
            variant = ProductVariant.objects.get(pk=item["variant_id"])
        except ProductVariant.DoesNotExist:
            raise DjangoValidationError({"variant_id": ["Variant not found."]}) from None
    _, movement = services.adjust_stock(
        product=product or variant.product, variant=variant, quantity_change=item["quantity_change"],
        reason=item["reason"], reference=item.get("reference", ""), note=item.get("note", ""), user=user,
    )
    return movement


@extend_schema(
    tags=["Admin – Products"], summary="Adjust stock for a single product or variant",
    request=StockAdjustmentSerializer, responses={200: StockMovementSerializer, 400: ERR},
)
class StockAdjustmentView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            movement = _apply_stock_adjustment(serializer.validated_data, request.user)
        except DjangoValidationError as exc:
            _raise(exc)
        return Response(StockMovementSerializer(movement).data)


@extend_schema_view(list=extend_schema(tags=["Admin – Products"], summary="Global inventory log", description="Filter by `product`, `variant`, `reason`."))
class AdminStockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = StockMovementSerializer
    queryset = StockMovement.objects.select_related("product", "variant", "user")
    filterset_fields = ["product", "variant", "reason"]
    ordering = ["-created_at"]


# --- gallery images (nested under a product) ------------------------------------------------


@extend_schema_view(
    list=extend_schema(tags=["Admin – Products"], summary="List a product's gallery images"),
    create=extend_schema(tags=["Admin – Products"], summary="Add a gallery image", responses={201: AdminProductImageSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Products"], summary="Update a gallery image (alt text, order)"),
    destroy=extend_schema(tags=["Admin – Products"], summary="Remove a gallery image"),
)
class AdminProductImageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminProductImageSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_product(self):
        return get_object_or_404(Product, pk=self.kwargs["product_pk"])

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ProductImage.objects.none()
        return ProductImage.objects.filter(product_id=self.kwargs["product_pk"])

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "product": self.get_product()}

    def perform_destroy(self, instance):
        image = instance.image
        instance.delete()
        discard_file(image)

    @extend_schema(
        tags=["Admin – Products"], summary="Reorder gallery images",
        description="Body: a list of image ids in the desired order.",
        request={"application/json": {"type": "array", "items": {"type": "integer"}}},
        responses={200: AdminProductImageSerializer(many=True)},
    )
    def reorder(self, request, product_pk=None):
        ids = request.data if isinstance(request.data, list) else request.data.get("order", [])
        images = {image.pk: image for image in self.get_queryset()}
        if set(ids) != set(images):
            raise ValidationError("Must list exactly the current image ids, in the new order.")
        for order, image_id in enumerate(ids):
            images[image_id].sort_order = order
        ProductImage.objects.bulk_update(images.values(), ["sort_order"])
        return Response(AdminProductImageSerializer(self.get_queryset(), many=True).data)


# --- variants (nested under a product) --------------------------------------------------------


@extend_schema_view(
    list=extend_schema(tags=["Admin – Products"], summary="List a product's variants"),
    create=extend_schema(tags=["Admin – Products"], summary="Add a variant", responses={201: AdminVariantSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Products"], summary="Update a variant", responses={200: AdminVariantSerializer, 400: ERR}),
    destroy=extend_schema(tags=["Admin – Products"], summary="Remove a variant"),
)
class AdminVariantViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminVariantSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_product(self):
        return get_object_or_404(Product, pk=self.kwargs["product_pk"])

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ProductVariant.objects.none()
        return ProductVariant.objects.filter(product_id=self.kwargs["product_pk"]).prefetch_related("attribute_values__attribute")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "product": self.get_product()}

    def perform_destroy(self, instance):
        image = instance.image
        instance.delete()
        discard_file(image)


# --- attributes & values -----------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(tags=["Admin – Products"], summary="List product attributes (e.g. Shade, Size)"),
    retrieve=extend_schema(tags=["Admin – Products"], summary="Get an attribute with its values"),
    create=extend_schema(tags=["Admin – Products"], summary="Create an attribute", responses={201: AdminProductAttributeSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Products"], summary="Rename an attribute"),
    destroy=extend_schema(tags=["Admin – Products"], summary="Delete an attribute (and its values)"),
)
class AdminProductAttributeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminProductAttributeSerializer
    queryset = ProductAttribute.objects.prefetch_related("values")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    search_fields = ["name"]
    ordering = ["name"]


@extend_schema_view(
    list=extend_schema(tags=["Admin – Products"], summary="List attribute values", description="Filter by `?attribute=<id>`."),
    create=extend_schema(tags=["Admin – Products"], summary="Add a value to an attribute", responses={201: AdminAttributeValueSerializer, 400: ERR}),
    partial_update=extend_schema(tags=["Admin – Products"], summary="Update a value"),
    destroy=extend_schema(tags=["Admin – Products"], summary="Delete a value"),
)
class AdminAttributeValueViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminAttributeValueSerializer
    queryset = AttributeValue.objects.select_related("attribute")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["attribute"]
    search_fields = ["value"]
    ordering = ["attribute__name", "value"]


@extend_schema_view(
    get=extend_schema(
        tags=["Admin – Products"], summary="Product picker",
        description=(
            "Lightweight, searchable product list (id, name, SKU, image) for admin dropdowns — "
            "e.g. choosing which products a video card links to. Published products only, capped "
            "at 20 results; narrow with `?search=`."
        ),
    )
)
class ProductPickerView(ListAPIView):
    """Reused wherever an admin needs to pick products from a search box, not just for videos."""

    permission_classes = [IsAdmin]
    serializer_class = ProductPickerSerializer
    queryset = Product.objects.filter(status="published").only("id", "name", "sku", "feature_image")
    search_fields = ["name", "sku"]
    pagination_class = None
    filter_backends = [filters.SearchFilter]

    def list(self, request, *args, **kwargs):
        # Slicing must happen AFTER filter_queryset() (SearchFilter can't filter a sliced queryset).
        queryset = self.filter_queryset(self.get_queryset())[:20]
        return Response(self.get_serializer(queryset, many=True).data)
