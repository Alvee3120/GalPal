"""Public endpoint: the frontend posts a browser event here for server-side (Meta CAPI) delivery."""
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.authentication import OptionalJWTAuthentication
from apps.core.serializers import ErrorResponseSerializer
from apps.site_settings.services import get_site_settings

from . import services
from .serializers import TrackEventSerializer
from .tasks import send_meta_event_task

ERR = OpenApiResponse(ErrorResponseSerializer)


class TrackEventView(APIView):
    """
    `PageView`/`ViewContent`/`AddToCart`/`InitiateCheckout` only — `Purchase` is fired automatically
    from order placement (see `signals.py`) and is never accepted here. Sent asynchronously (Celery);
    the response doesn't wait on Meta, so a slow or unreachable Meta never slows down the page.
    """

    authentication_classes = [OptionalJWTAuthentication]  # a stale token must not break tracking
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Tracking"], summary="Report a browser event for server-side delivery to Meta",
        description="`event_id`, if sent, should be the same id the frontend gives its own Pixel call for this event, so Meta can merge (dedupe) the two.",
        request=TrackEventSerializer, responses={202: None, 400: ERR},
    )
    def post(self, request):
        serializer = TrackEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        site = get_site_settings()

        user_data = services.build_user_data(
            user=request.user if request.user.is_authenticated else None,
            fbp=data.get("fbp", ""), fbc=data.get("fbc", ""),
            client_ip=request.META.get("REMOTE_ADDR", ""), user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        custom_data = {}
        if "product_id" in data:
            custom_data["content_ids"] = [data["product_id"]]
            custom_data["content_type"] = "product"
        if "value" in data:
            custom_data["value"] = str(data["value"])
            custom_data["currency"] = data.get("currency") or site.currency_code

        send_meta_event_task.delay(
            event_name=data["event_name"], event_id=data.get("event_id", ""), user_data=user_data,
            custom_data=custom_data or None, event_source_url=data.get("event_source_url", ""),
            user_id=request.user.pk if request.user.is_authenticated else None,
        )
        return Response(status=status.HTTP_202_ACCEPTED)
