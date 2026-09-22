"""Public endpoint: the payment gateway's IPN/webhook callback."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import ErrorResponseSerializer

from . import services

ERR = OpenApiResponse(ErrorResponseSerializer)


class PaymentCallbackView(APIView):
    """
    The gateway's IPN/webhook. No JWT here — the gateway proves itself with a signature (checked by
    the named gateway's own `parse_callback`), exactly like a real payment provider's callback.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Payments"], summary="Gateway callback (IPN)",
        description="The raw body and headers are handed to the named gateway for signature verification and parsing. Always 400 on any problem — signature, payload shape, or an unknown reference — so nothing about which failed is revealed to a caller that hasn't proven itself. The stub gateway expects `{reference, status, amount}` plus an `X-Stub-Signature` header (HMAC-SHA256 of the raw body).",
        request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT, 400: ERR},
    )
    def post(self, request, gateway):
        services.handle_callback(gateway, request.body, request.headers)
        return Response({"status": "ok"})
