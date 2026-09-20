"""Public (storefront) product endpoints."""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import services
from .filters_product import PublicProductFilter, annotate_effective_price
from .models import Product, ProductStatus
from .serializers_product import PublicProductDetailSerializer, PublicProductListSerializer

_ORDERING_ALIASES = {"price": "effective_price_db", "newest": "created_at", "popularity": "popularity_db", "rating": "average_rating"}


class ProductOrderingFilter(filters.OrderingFilter):
    """Translates friendly `?ordering=price|newest|popularity|rating` into the real (annotated) field."""

    def get_ordering(self, request, queryset, view):
        raw = request.query_params.get(self.ordering_param)
        if not raw:
            return self.get_default_ordering(view)
        translated = []
        for term in raw.split(","):
            term = term.strip()
            negate = term.startswith("-")
            key = term[1:] if negate else term
            key = _ORDERING_ALIASES.get(key, key)
            translated.append(f"-{key}" if negate else key)
        ordering = self.remove_invalid_fields(queryset, translated, view, request)
        return ordering or self.get_default_ordering(view)


@extend_schema_view(
    list=extend_schema(
        tags=["Catalog"], summary="List products",
        description=(
            "Published products only. Filters: `category` (slug, includes sub-categories), `brand` (slug), "
            "`tag` (slug), `skin_type`, `gender`, `price_min`/`price_max`, `in_stock`, `on_sale`, "
            "`is_featured`/`is_new_arrival`/`is_bestseller`. Search: name, SKU, brand, tags. "
            "Order by `ordering=price|-price|newest|popularity|rating`."
        ),
        parameters=[OpenApiParameter("ordering", str, description="price, -price, newest, popularity, rating")],
    ),
    retrieve=extend_schema(
        tags=["Catalog"], summary="Product by slug",
        description="Includes gallery, active variants, breadcrumb (via the primary category) and related products.",
    ),
)
class PublicProductViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = []
    permission_classes = [AllowAny]
    lookup_field = "slug"
    filterset_class = PublicProductFilter
    search_fields = ["name", "sku", "brand__name", "tags__name"]
    ordering_fields = ["effective_price_db", "created_at", "average_rating", "popularity_db"]
    ordering = ["-created_at"]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, ProductOrderingFilter]

    def get_queryset(self):
        queryset = Product.objects.filter(status=ProductStatus.PUBLISHED).select_related("brand").prefetch_related(
            "category_links__category", "tags", "images", "variants__attribute_values__attribute"
        )
        return annotate_effective_price(queryset)

    def get_serializer_class(self):
        return PublicProductDetailSerializer if self.action == "retrieve" else PublicProductListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "retrieve":
            context["index"] = services.CategoryIndex()
        return context

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        context = self.get_serializer_context()
        link = next((link for link in instance.category_links.all() if link.is_primary), None)
        if link:
            context["related_products"] = list(
                self.get_queryset().filter(category_links__category_id=link.category_id).exclude(pk=instance.pk).distinct()[:8]
            )
        serializer = self.get_serializer(instance, context=context)
        return Response(serializer.data)
