"""Public storefront view of Admin discounts (homepage sections), mounted at /api/v1/. No login needed."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import DiscountKind


class ActiveDiscountSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    type = serializers.ChoiceField(choices=DiscountKind.choices, source="kind")
    value = serializers.DecimalField(max_digits=12, decimal_places=2)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    product_count = serializers.IntegerField()


class ActiveDiscountListView(APIView):
    authentication_classes = []  # a stale token must not break a public page
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Catalog"], summary="Active discounts",
        description="Admin discounts that are switched on and inside their start/end window right now, each with how many "
                    "published products it is pricing (discounts pricing nothing are left out). The products themselves: "
                    "GET /products/?discount=<id>. Not paginated.",
        responses=ActiveDiscountSerializer(many=True),
    )
    def get(self, request):
        rows = [
            {"id": r.id, "name": r.name, "kind": r.kind, "value": r.value, "starts_at": r.starts_at, "ends_at": r.ends_at,
             "product_count": len(ids)}
            for r, ids in services.storefront_discounts()
        ]
        return Response(ActiveDiscountSerializer(rows, many=True).data)
