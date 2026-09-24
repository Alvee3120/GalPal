"""Admin endpoints: full review CRUD, moderation (approve/reject), replies, and manual/testimonial
reviews. Admin only, except moderation: CCE may list, view, approve, reject and delete reviews
(IsCatalogStaff via `cce_actions`); editing, replying and manual reviews stay Admin only."""
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import CatalogStaffActionsMixin, IsAdmin
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .filters import AdminReviewFilter
from .models import Review
from .serializers import AdminReviewSerializer, ManualReviewSerializer, ReplySerializer, ReviewStatusChangeSerializer

ERR = OpenApiResponse(ErrorResponseSerializer)
TAG = ["Admin – Reviews"]


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="List reviews (every status)", description="Filters: `status`, `is_verified_purchase`, `is_manual`, `rating`, `product` (slug). `search` matches the reviewer name, text or product name."),
    retrieve=extend_schema(tags=TAG, summary="Review detail"),
    partial_update=extend_schema(tags=TAG, summary="Edit a review", responses={200: AdminReviewSerializer, 400: ERR}),
    destroy=extend_schema(tags=TAG, summary="Delete a review", description="Removes it and its images, and the product's rating is recomputed.", responses={204: None}),
)
class AdminReviewViewSet(CatalogStaffActionsMixin, viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    cce_actions = frozenset({"list", "retrieve", "approve", "reject", "destroy"})  # CCE Review Management
    queryset = Review.objects.select_related("product", "user", "replied_by", "created_by").prefetch_related("images")
    serializer_class = AdminReviewSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_class = AdminReviewFilter
    search_fields = ["reviewer_name", "text", "product__name", "product__sku", "user__phone"]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    def perform_destroy(self, instance):
        services.delete_review(instance)

    def _detail(self, review, status_code=status.HTTP_200_OK):
        fresh = self.get_queryset().get(pk=review.pk)
        return Response(AdminReviewSerializer(fresh, context=self.get_serializer_context()).data, status=status_code)

    @extend_schema(
        tags=TAG, summary="Create a manual/testimonial review",
        description="A product, a name, a star rating and text — no customer account. Defaults to approved.",
        request=ManualReviewSerializer, responses={201: AdminReviewSerializer, 400: ERR},
    )
    def create(self, request, *args, **kwargs):
        serializer = ManualReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        review = services.create_manual_review(
            product=data["product"], reviewer_name=data["reviewer_name"], rating=data["rating"],
            title=data.get("title", ""), text=data["text"], status=data["status"], created_by=request.user,
            images=data.get("images"),
        )
        return self._detail(review, status.HTTP_201_CREATED)

    @extend_schema(tags=TAG, summary="Change moderation status", request=ReviewStatusChangeSerializer, responses={200: AdminReviewSerializer, 400: ERR})
    @action(detail=True, methods=["post"], url_path="status")
    def change_status(self, request, pk=None):
        review = self.get_object()
        serializer = ReviewStatusChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_status(review, serializer.validated_data["status"], user=request.user)
        return self._detail(review)

    @extend_schema(tags=TAG, summary="Approve a review", responses={200: AdminReviewSerializer})
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        review = self.get_object()
        services.approve(review, user=request.user)
        return self._detail(review)

    @extend_schema(tags=TAG, summary="Reject a review", responses={200: AdminReviewSerializer})
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        review = self.get_object()
        services.reject(review, user=request.user)
        return self._detail(review)

    @extend_schema(tags=TAG, summary="Reply to a review", request=ReplySerializer, responses={200: AdminReviewSerializer, 400: ERR})
    @action(detail=True, methods=["post"], url_path="reply")
    def reply(self, request, pk=None):
        review = self.get_object()
        serializer = ReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.reply(review, user=request.user, text=serializer.validated_data["text"])
        return self._detail(review)
