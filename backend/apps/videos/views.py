"""Public endpoint: active video cards with their linked products' shoppable card data."""

from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from . import services
from .serializers import PublicVideoCardSerializer


@extend_schema(
    tags=["Video Cards"], summary="List active video cards",
    description="Each card includes its linked products (published only) as shoppable cards: id, name, slug, image, price.",
)
class PublicVideoCardListView(ListAPIView):
    """List only, deliberately: there is no public detail-by-id route for a video card."""

    authentication_classes = []  # a stale token must not break a public page
    permission_classes = [AllowAny]
    serializer_class = PublicVideoCardSerializer

    def get_queryset(self):
        return services.visible_videos()
