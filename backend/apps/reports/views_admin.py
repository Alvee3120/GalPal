"""CSV exports (Module 17), mounted at /api/v1/admin/reports/export/. Admin only (IsAdmin): CCE and customers get 403.

The report figures themselves are part of GET /admin/dashboard/ (`reports`)."""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.core.serializers import ErrorResponseSerializer
from apps.orders import analytics
from apps.orders.models import OrderSource, OrderStatus
from apps.orders.views_admin import DashboardQuerySerializer

from . import exports

TAG = ["Admin – Reports"]
ERR = OpenApiResponse(ErrorResponseSerializer)
RANGE = [OpenApiParameter("date_from", OpenApiTypes.DATE), OpenApiParameter("date_to", OpenApiTypes.DATE)]
CSV = {(200, "text/csv"): OpenApiResponse(description="CSV file"), 400: ERR}


def _range(request):
    query = DashboardQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    return query.validated_data.get("date_from"), query.validated_data.get("date_to")


class OrderExportQuerySerializer(DashboardQuerySerializer):
    status = serializers.ChoiceField(choices=OrderStatus.choices, required=False)
    source = serializers.ChoiceField(choices=OrderSource.choices, required=False)


class OrderExportView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=TAG, summary="Export orders (CSV)", description="Orders placed in the range (default last 30 days), "
                   "optionally one `status` / `source`. Includes source, staff, shipping zone and charge.",
                   parameters=[*RANGE, OpenApiParameter("status", str), OpenApiParameter("source", str)], responses=CSV)
    def get(self, request):
        query = OrderExportQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        date_from, date_to = data.get("date_from"), data.get("date_to")
        if date_from is None:
            date_from, date_to = analytics.default_range()
        return exports.export_orders(date_from=date_from, date_to=date_to, status=data.get("status"), source=data.get("source"))


class ProductExportView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=TAG, summary="Export products (CSV)", description="Every product (not deleted), with stock.", responses=CSV)
    def get(self, request):
        return exports.export_products()


class CustomerExportView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=TAG, summary="Export customers (CSV)", description="Customer accounts with order totals; with a "
                   "date range, only those who joined in it.", parameters=RANGE, responses=CSV)
    def get(self, request):
        date_from, date_to = _range(request)
        return exports.export_customers(date_from=date_from, date_to=date_to)
