"""Public endpoint: the homepage hero slider (config + banners in one response)."""

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import HeroSliderSerializer


class HeroSliderView(APIView):
    authentication_classes = []  # a stale token must not break a public page
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Hero Banners"], summary="Homepage hero slider",
        description="Active, in-schedule banners in display order, plus the slider-wide config (delay, autoplay, loop).",
        responses=HeroSliderSerializer,
    )
    def get(self, request):
        data = {"config": services.get_slider_config(), "banners": services.visible_banners()}
        return Response(HeroSliderSerializer(data, context={"request": request}).data)
