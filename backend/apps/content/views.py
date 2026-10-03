"""Public storefront endpoints for Module 15, mounted at /api/v1/. No login needed."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import ErrorResponseSerializer

from . import services
from .models import Faq, Page
from .serializers import (
    PublicAnnouncementSerializer,
    PublicFaqSerializer,
    PublicPageSerializer,
    SearchResultSerializer,
    SubscribeInputSerializer,
    UnsubscribeInputSerializer,
)
from .throttles import NewsletterThrottle, SearchThrottle

TAG = ["Content"]
ERR = OpenApiResponse(ErrorResponseSerializer)


class _Public(APIView):
    authentication_classes = []  # a stale token must not break a public page
    permission_classes = [AllowAny]


class PageDetailView(_Public):
    @extend_schema(tags=TAG, summary="Content page by slug", description="Active pages only (about, privacy-policy, "
                   "terms, return-and-cancellation-policy, shipping-policy, or any custom slug).",
                   responses={200: PublicPageSerializer, 404: ERR})
    def get(self, request, slug):
        page = Page.objects.filter(slug=slug, is_active=True).first()
        if page is None:
            raise NotFound("Page not found.")
        return Response(PublicPageSerializer(page).data)


class FaqListView(_Public):
    @extend_schema(tags=TAG, summary="FAQs", description="Active questions, ordered by category then sort order. Not paginated.",
                   responses={200: PublicFaqSerializer(many=True)})
    def get(self, request):
        return Response(PublicFaqSerializer(Faq.objects.filter(is_active=True), many=True).data)


class AnnouncementListView(_Public):
    @extend_schema(tags=TAG, summary="Live announcement bar items", description="Active and inside their time window.",
                   responses={200: PublicAnnouncementSerializer(many=True)})
    def get(self, request):
        return Response(PublicAnnouncementSerializer(services.live_announcements(), many=True).data)


class NewsletterSubscribeView(_Public):
    throttle_classes = [NewsletterThrottle]

    @extend_schema(tags=TAG, summary="Subscribe to the newsletter", description="An email and/or a phone. The reply is "
                   "the same for new and existing subscribers. Throttled per IP.",
                   request=SubscribeInputSerializer, responses={201: OpenApiResponse(description="{ok: true}"), 400: ERR, 429: ERR})
    def post(self, request):
        data = SubscribeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.subscribe(**data.validated_data, ip_address=request.META.get("REMOTE_ADDR"))
        return Response({"ok": True}, status=status.HTTP_201_CREATED)


class NewsletterUnsubscribeView(_Public):
    throttle_classes = [NewsletterThrottle]

    @extend_schema(tags=TAG, summary="Unsubscribe with the link token", request=UnsubscribeInputSerializer,
                   responses={200: OpenApiResponse(description="{ok: true}"), 404: ERR, 429: ERR})
    def post(self, request):
        data = UnsubscribeInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if not services.unsubscribe(data.validated_data["token"]):
            raise NotFound("This unsubscribe link is invalid.")
        return Response({"ok": True})


class SearchView(_Public):
    throttle_classes = [SearchThrottle]

    @extend_schema(
        tags=TAG, summary="Global search + autocomplete",
        description="Published products, visible categories and active brands whose name matches `q` (products also by "
                    "SKU, brand and tag), best matches first, plus `suggestions` for autocomplete. `q` needs 2+ characters.",
        parameters=[
            OpenApiParameter("q", str, description="Search text"),
            OpenApiParameter("limit", int, description="Items per group, 1–20 (default 6)"),
        ],
        responses={200: SearchResultSerializer},
    )
    def get(self, request):
        try:
            limit = min(max(int(request.query_params.get("limit", 6)), 1), 20)
        except ValueError:
            limit = 6
        result = services.global_search(request.query_params.get("q", ""), limit=limit)
        return Response(SearchResultSerializer(result, context={"request": request}).data)
