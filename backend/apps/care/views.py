"""Public endpoints for Module 14 (contact form, checkout capture), mounted at /api/v1/."""

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart import services as cart_services
from apps.core.authentication import OptionalJWTAuthentication
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .serializers import (
    CheckoutLeadInputSerializer,
    ContactMessageInputSerializer,
)
from .throttles import CheckoutLeadThrottle, ContactThrottle

TAG = ["Customer Care"]
ERR = OpenApiResponse(ErrorResponseSerializer)


class ContactMessageView(APIView):
    """The public contact form (storefront /contact). Goes to the Admin support inbox."""

    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [ContactThrottle]

    @extend_schema(
        tags=TAG, summary="Send a contact message",
        description="Name + message, and a phone or an email so we can reply. Throttled per IP.",
        request=ContactMessageInputSerializer, responses={201: OpenApiResponse(description="{ok: true}"), 400: ERR, 429: ERR},
    )
    def post(self, request):
        data = ContactMessageInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.submit_contact_message(data=data.validated_data, user=request.user, ip_address=request.META.get("REMOTE_ADDR"))
        return Response({"ok": True}, status=status.HTTP_201_CREATED)


class CheckoutLeadView(APIView):
    """
    Called by the checkout page once the shopper has entered a name and a valid phone: remembers the checkout so
    Admin can follow up if no order follows. Silent and harmless — never blocks or changes the checkout.
    """

    authentication_classes = [OptionalJWTAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [CheckoutLeadThrottle]

    @extend_schema(
        tags=TAG, summary="Capture a checkout in progress",
        description="Name + phone (+ email/district) at the checkout step; the cart comes from the login or X-Cart-Token.",
        request=CheckoutLeadInputSerializer, responses={204: None, 400: ERR, 429: ERR},
    )
    def post(self, request):
        data = CheckoutLeadInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            services.capture_checkout_lead(**data.validated_data, user=request.user, cart=cart_services.get_cart(request))
        except DjangoValidationError:
            pass  # an invalid phone just isn't captured; the checkout page validates it for real
        return Response(status=status.HTTP_204_NO_CONTENT)
