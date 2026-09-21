"""Admin endpoints: delivery zones (charges, coverage, thresholds), charge history and delivery methods.
Admin only (CCE gets 403 — shipping is not part of the order module CCE is scoped to)."""
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin
from apps.catalog.exceptions import Conflict
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .models import DeliveryMethod, DeliveryZone, ShippingChargeHistory
from .serializers import (
    AdminDeliveryMethodSerializer,
    AdminZoneSerializer,
    ChargeHistorySerializer,
    ZoneChargeSerializer,
)

ERR = OpenApiResponse(ErrorResponseSerializer)
TAG = ["Admin – Shipping"]


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="List delivery zones (including inactive)"),
    retrieve=extend_schema(tags=TAG, summary="Get a delivery zone"),
    create=extend_schema(
        tags=TAG, summary="Create a delivery zone", responses={201: AdminZoneSerializer, 400: ERR},
        description="`coverage` lists `{district_id, areas}`; empty `areas` means the whole district.",
    ),
    partial_update=extend_schema(
        tags=TAG, summary="Update a delivery zone", responses={200: AdminZoneSerializer, 400: ERR},
        description=(
            "Any field, including `charge`, `estimated_days_*`, `free_shipping_threshold` (blank = global, 0 = never free), "
            "`is_active` and `coverage` (sent = replaces the zone's districts). The default zone can't be unset or deactivated: "
            "mark another zone `is_default` instead."
        ),
    ),
    destroy=extend_schema(
        tags=TAG, summary="Delete a delivery zone",
        description="Blocked (409) for the default zone and for a zone that orders were placed with; deactivate those instead.",
        responses={204: None, 409: ERR},
    ),
)
class AdminZoneViewSet(viewsets.ModelViewSet):
    serializer_class = AdminZoneSerializer
    permission_classes = [IsAdmin]
    queryset = DeliveryZone.objects.prefetch_related("coverage__district")
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["is_active", "is_default"]
    search_fields = ["name", "slug"]
    ordering_fields = ["sort_order", "name", "charge", "created_at"]
    ordering = ["sort_order", "id"]

    def perform_destroy(self, instance):
        services.delete_zone(instance)

    @extend_schema(
        tags=TAG, summary="Change only a zone's delivery charge",
        description="The quick \"change delivery fee\" edit. Logged in the zone's history; applies to the next calculation immediately and never to existing orders.",
        request=ZoneChargeSerializer, responses={200: AdminZoneSerializer, 400: ERR},
    )
    @action(detail=True, methods=["patch"], url_path="charge")
    def charge(self, request, pk=None):
        zone = self.get_object()
        serializer = ZoneChargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        zone = services.change_charge(zone, serializer.validated_data["charge"], user=request.user)
        zone = self.get_queryset().get(pk=zone.pk)
        return Response(AdminZoneSerializer(zone, context=self.get_serializer_context()).data)

    @extend_schema(
        tags=TAG, summary="A zone's charge history", responses=ChargeHistorySerializer(many=True),
        description="Newest first: who changed the charge, from what to what, and when.",
    )
    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        zone = self.get_object()
        entries = ShippingChargeHistory.objects.filter(zone=zone).select_related("changed_by")
        page = self.paginate_queryset(entries)
        return self.get_paginated_response(ChargeHistorySerializer(page, many=True).data)


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="List delivery methods (including inactive)"),
    retrieve=extend_schema(tags=TAG, summary="Get a delivery method"),
    create=extend_schema(tags=TAG, summary="Create a delivery method", responses={201: AdminDeliveryMethodSerializer, 400: ERR}),
    partial_update=extend_schema(tags=TAG, summary="Update a delivery method", responses={200: AdminDeliveryMethodSerializer, 400: ERR}),
    destroy=extend_schema(
        tags=TAG, summary="Delete a delivery method",
        description="Blocked (409) once orders used it; deactivate it instead.", responses={204: None, 409: ERR},
    ),
)
class AdminDeliveryMethodViewSet(viewsets.ModelViewSet):
    serializer_class = AdminDeliveryMethodSerializer
    permission_classes = [IsAdmin]
    queryset = DeliveryMethod.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    filterset_fields = ["is_active"]
    search_fields = ["name", "slug"]
    ordering = ["sort_order", "id"]

    def perform_destroy(self, instance):
        if services.has_orders(instance):
            raise Conflict(
                "Orders were placed with this delivery method. Deactivate it instead of deleting it.", code="method_in_use"
            )
        instance.delete()
