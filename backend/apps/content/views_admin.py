"""Admin endpoints for Module 15, mounted at /api/v1/admin/content/. Admin only (IsAdmin): CCE and customers get 403."""

import csv

from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin

from . import services
from .models import Announcement, Faq, HomepageCategorySection, NewsletterSubscriber, Page
from .serializers import (
    AdminAnnouncementSerializer,
    AdminFaqSerializer,
    AdminHomepageCategorySectionSerializer,
    AdminPageSerializer,
    AdminSubscriberSerializer,
)

TAG = ["Admin – Content"]


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="Content pages", description="`search` title/slug. Includes `standard_pages`."),
    retrieve=extend_schema(tags=TAG, summary="Content page"),
    create=extend_schema(tags=TAG, summary="Create a content page"),
    partial_update=extend_schema(tags=TAG, summary="Update a content page"),
    destroy=extend_schema(tags=TAG, summary="Delete a content page", description="A standard page falls back to the "
                          "storefront's built-in text."),
)
class PageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminPageSerializer
    queryset = Page.objects.select_related("updated_by")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [filters.SearchFilter]
    search_fields = ["title", "slug"]
    pagination_class = None  # a handful of pages

    def perform_create(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @extend_schema(tags=TAG, summary="Standard pages", description="The storefront pages a CMS page can replace: "
                   "`{slug: default title}`.", responses={200: OpenApiResponse(description="{slug: title}")})
    @action(detail=False, url_path="standard")
    def standard(self, request):
        return Response(services.STANDARD_PAGES)


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="FAQs", description="All FAQs (active and hidden). `search`, `category`, `is_active`."),
    create=extend_schema(tags=TAG, summary="Add an FAQ"),
    partial_update=extend_schema(tags=TAG, summary="Update an FAQ"),
    destroy=extend_schema(tags=TAG, summary="Delete an FAQ"),
)
class FaqViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminFaqSerializer
    queryset = Faq.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["category", "is_active"]
    search_fields = ["question", "answer", "category"]
    pagination_class = None


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="Newsletter subscribers", description="`is_subscribed`, `search` email/phone."),
    partial_update=extend_schema(tags=TAG, summary="Subscribe / unsubscribe one subscriber", description="Only `is_subscribed`."),
    destroy=extend_schema(tags=TAG, summary="Delete a subscriber"),
)
class SubscriberViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminSubscriberSerializer
    queryset = NewsletterSubscriber.objects.all()
    http_method_names = ["get", "patch", "delete", "head", "options"]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_subscribed"]
    search_fields = ["email", "phone"]

    def perform_update(self, serializer):
        subscribed = serializer.validated_data.get("is_subscribed")
        if subscribed is not None:
            services.set_subscribed(serializer.instance, subscribed)

    @extend_schema(tags=TAG, summary="Export subscribed contacts (CSV)", description="Current subscribers only.",
                   responses={(200, "text/csv"): OpenApiResponse(description="CSV file")})
    @action(detail=False, url_path="export")
    def export(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="newsletter-{timezone.localdate():%Y-%m-%d}.csv"'
        response.write("﻿")  # BOM so Excel reads UTF-8
        writer = csv.writer(response)
        writer.writerow(["Email", "Phone", "Source", "Subscribed at"])
        for sub in NewsletterSubscriber.objects.filter(is_subscribed=True).order_by("created_at").iterator():
            writer.writerow([sub.email or "", sub.phone or "", sub.source, timezone.localtime(sub.created_at).strftime("%Y-%m-%d %H:%M")])
        return response


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="Announcement bar items"),
    create=extend_schema(tags=TAG, summary="Add an announcement"),
    partial_update=extend_schema(tags=TAG, summary="Update an announcement"),
    destroy=extend_schema(tags=TAG, summary="Delete an announcement"),
)
class AnnouncementViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminAnnouncementSerializer
    queryset = Announcement.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    pagination_class = None


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="Homepage product sections", description="Product sections around the skincare "
                       "video section: a category (titled with its name) or the Trending / New Arrivals / Bestsellers product "
                       "flags (with an editable title)."),
    create=extend_schema(tags=TAG, summary="Add a homepage product section"),
    partial_update=extend_schema(tags=TAG, summary="Edit a homepage product section"),
    destroy=extend_schema(tags=TAG, summary="Remove a homepage product section"),
)
class HomepageCategorySectionViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                                     viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminHomepageCategorySectionSerializer
    queryset = HomepageCategorySection.objects.select_related("category")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    pagination_class = None
