"""Wishlist endpoints (Module 7), mounted at /api/v1/. Logged-in users only (a guest gets 401 and is asked to log in)."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.serializers_product import PublicProductListSerializer
from apps.core.serializers import ErrorResponseSerializer

from . import wishlist

TAG = ["Wishlist"]
ERR = OpenApiResponse(ErrorResponseSerializer)


class WishlistAddSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()


class WishlistSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    product_ids = serializers.ListField(child=serializers.IntegerField(), help_text="For quick 'is it saved?' checks")
    products = PublicProductListSerializer(many=True)


def _payload(request):
    items = wishlist.products(request.user)
    return {
        "count": len(items),
        "product_ids": [p.pk for p in items],
        "products": PublicProductListSerializer(items, many=True, context={"request": request}).data,
    }


class WishlistView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="My wishlist", description="Saved products that are still published, newest first.",
                   responses={200: WishlistSerializer, 401: ERR})
    def get(self, request):
        return Response(_payload(request))

    @extend_schema(tags=TAG, summary="Save a product", description="Idempotent: saving it again changes nothing.",
                   request=WishlistAddSerializer, responses={201: WishlistSerializer, 200: WishlistSerializer, 400: ERR, 401: ERR})
    def post(self, request):
        data = WishlistAddSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        _, created = wishlist.add(request.user, data.validated_data["product_id"])
        return Response(_payload(request), status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WishlistItemView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAG, summary="Remove a product", responses={200: WishlistSerializer, 401: ERR})
    def delete(self, request, product_id):
        wishlist.remove(request.user, product_id)  # removing something that isn't there is fine
        return Response(_payload(request))
