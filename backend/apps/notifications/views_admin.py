"""Admin endpoints for Module 16, mounted at /api/v1/admin/notifications/. Admin only (IsAdmin): CCE and customers get 403."""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin
from apps.core.serializers import ErrorResponseSerializer

from . import services
from .exceptions import field_error
from .models import Channel, Event, NotificationLog, NotificationTemplate
from .serializers import NotificationLogSerializer, TemplateInputSerializer, TemplateSerializer

TAG = ["Admin – Notifications"]
ERR = OpenApiResponse(ErrorResponseSerializer)


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="Notification log", description="Every email/SMS sent. Filter `event`, `channel`, "
                       "`status`; `search` recipient or order number. Secrets in bodies are masked."),
    retrieve=extend_schema(tags=TAG, summary="One notification"),
)
class NotificationLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = NotificationLogSerializer
    queryset = NotificationLog.objects.select_related("order")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["event", "channel", "status"]
    search_fields = ["recipient", "order__number"]

    @extend_schema(tags=TAG, summary="Re-send a failed notification", request=None,
                   description="Not for messages that held a code/password (those aren't stored).",
                   responses={200: NotificationLogSerializer, 400: ERR})
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        log = services.resend(self.get_object())
        return Response(self.get_serializer(log).data)


def _template_data(event, channel):
    default = services.DEFAULT_TEMPLATES.get((event, channel), ("", ""))
    row = NotificationTemplate.objects.filter(event=event, channel=channel).first()
    return {
        "event": event, "event_label": Event(event).label, "channel": channel,
        "subject": row.subject if row else default[0], "body": row.body if row else default[1],
        "is_active": row.is_active if row else bool(default[1]), "is_custom": row is not None,
        "placeholders": services.PLACEHOLDERS[event], "secret_placeholder": services.SECRET_PLACEHOLDERS.get(event),
        "default_subject": default[0], "default_body": default[1],
    }


def _check(event, channel):
    if event not in Event.values or channel not in Channel.values:
        raise NotFound("Unknown event or channel.")


class TemplateListView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=TAG, summary="Message templates", description="Every event × channel, with the text in use. "
                   "A channel with no built-in text starts switched off.", responses={200: TemplateSerializer(many=True)})
    def get(self, request):
        return Response([_template_data(e, c) for e in Event.values for c in Channel.values])


class TemplateDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=TAG, summary="Save a message template", request=TemplateInputSerializer,
                   responses={200: TemplateSerializer, 400: ERR, 404: ERR})
    def put(self, request, event, channel):
        _check(event, channel)
        data = TemplateInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        subject = data.validated_data.get("subject", "").strip() if channel == Channel.EMAIL else ""
        body = data.validated_data["body"].strip()
        unknown = services.unknown_placeholders(event, subject, body)
        if unknown:
            raise field_error("body", f"Unknown placeholder(s): {', '.join('{' + u + '}' for u in unknown)}.", "unknown_placeholder")
        secret = services.SECRET_PLACEHOLDERS.get(event)
        if secret and "{" + secret + "}" not in body:
            raise field_error("body", f"This message must include {{{secret}}}.", "missing_placeholder")
        if channel == Channel.EMAIL and not subject:
            raise field_error("subject", "An email needs a subject.", "required")
        NotificationTemplate.objects.update_or_create(
            event=event, channel=channel,
            defaults={"subject": subject, "body": body, "is_active": data.validated_data["is_active"], "updated_by": request.user},
        )
        return Response(_template_data(event, channel))

    @extend_schema(tags=TAG, summary="Reset a template to the built-in text", responses={200: TemplateSerializer})
    def delete(self, request, event, channel):
        _check(event, channel)
        NotificationTemplate.objects.filter(event=event, channel=channel).delete()
        return Response(_template_data(event, channel), status=status.HTTP_200_OK)
