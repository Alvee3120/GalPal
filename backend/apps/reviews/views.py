"""
Public review endpoints: list a product's approved reviews, its rating breakdown, and a customer's
own POST to create a review.
"""
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.core.authentication import OptionalJWTAuthentication
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .filters import PublicReviewFilter
from .models import Review, ReviewStatus
from .serializers import CreateReviewSerializer, PublicReviewSerializer, RatingBreakdownSerializer

ERR = OpenApiResponse(ErrorResponseSerializer)
TAG = ["Reviews"]


@extend_schema_view(
    get=extend_schema(
        tags=TAG, summary="List a product's approved reviews",
        description="Filter with `?product=<slug>` (or `?rating=<1-5>`). Newest first.",
    ),
    post=extend_schema(
        tags=TAG, summary="Write a review",
        description="Customer only. One review per product per customer (409 `already_reviewed` on a repeat). `images`: up to 5, multipart.",
        request=CreateReviewSerializer, responses={201: PublicReviewSerializer, 400: ERR, 403: ERR, 409: ERR},
    ),
)
class ReviewListCreateView(generics.ListCreateAPIView):
    authentication_classes = [OptionalJWTAuthentication]  # a stale token must not break the public list
    filterset_class = PublicReviewFilter
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def get_permissions(self):
        return [IsAuthenticated()] if self.request.method == "POST" else [AllowAny()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Review.objects.none()
        return Review.objects.filter(status=ReviewStatus.APPROVED).select_related("product").prefetch_related("images")

    def get_serializer_class(self):
        return CreateReviewSerializer if self.request.method == "POST" else PublicReviewSerializer

    def create(self, request, *args, **kwargs):
        if request.user.role != User.Role.CUSTOMER:
            raise PermissionDenied("Only a customer account can write a review.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        review = services.create_review(
            product=data["product"], user=request.user, rating=data["rating"],
            title=data.get("title", ""), text=data["text"], images=data.get("images"),
        )
        return Response(PublicReviewSerializer(review, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)


class RatingBreakdownView(generics.GenericAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=TAG, summary="A product's rating breakdown",
        description="`?product=<slug>` is required. Star counts are of approved reviews only.",
        parameters=[OpenApiParameter("product", str, required=True, description="Product slug")],
        responses={200: RatingBreakdownSerializer, 404: ERR},
    )
    def get(self, request):
        product = get_object_or_404(Product, slug=request.query_params.get("product", ""))
        breakdown = services.rating_breakdown(product)
        body = {"average_rating": product.average_rating, "review_count": product.review_count, "breakdown": {str(k): v for k, v in breakdown.items()}}
        return Response(RatingBreakdownSerializer(body).data)
