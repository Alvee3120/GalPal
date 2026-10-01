"""Admin endpoints for Module 14, mounted at /api/v1/admin/care/. Admin only (IsAdmin): CCE and customers get 403."""

from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAdmin
from apps.core.serializers import ErrorResponseSerializer
from apps.orders.models import Order

from . import services
from .models import CheckoutLead, CheckoutLeadStatus, ContactMessage, CustomerNote, CustomerTag, ReturnRequest
from .serializers import (
    AdminCheckoutLeadSerializer,
    AdminContactMessageSerializer,
    AdminReturnRequestSerializer,
    CustomerNoteSerializer,
    CustomerProfileSerializer,
    CustomerTagSerializer,
    NoteInputSerializer,
    SetTagsSerializer,
)

TAG = ["Admin – Customer Care"]
ERR = OpenApiResponse(ErrorResponseSerializer)


def _customer(pk):
    customer = User.objects.filter(pk=pk, role=User.Role.CUSTOMER).first()
    if customer is None:
        raise NotFound("Customer not found.")
    return customer


def _profile(customer, request):
    data = {
        **{f: getattr(customer, f) for f in ("id", "full_name", "phone", "email", "avatar", "is_active", "created_via_checkout", "created_at", "last_login")},
        "stats": services.customer_stats(customer),
        "tags": customer.care_tags.all(),
        "notes": customer.care_notes.select_related("author")[:50],
        "recent_orders": Order.objects.filter(customer=customer).order_by("-created_at")[:20],
    }
    return CustomerProfileSerializer(data, context={"request": request}).data


class CustomerProfileView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=TAG, summary="Customer care profile", description="Account, order stats (total spent excludes "
                   "cancelled/failed/returned orders), tags, care notes and recent orders.", responses={200: CustomerProfileSerializer, 404: ERR})
    def get(self, request, pk):
        return Response(_profile(_customer(pk), request))


class CustomerNotesView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=TAG, summary="Add a care note", request=NoteInputSerializer, responses={201: CustomerNoteSerializer, 400: ERR})
    def post(self, request, pk):
        note = services.add_customer_note(_customer(pk), request.user, request.data.get("text"))
        return Response(CustomerNoteSerializer(note).data, status=status.HTTP_201_CREATED)


class CustomerNoteDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=TAG, summary="Delete a care note", responses={204: None})
    def delete(self, request, pk):
        CustomerNote.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CustomerTagsView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=TAG, summary="Set a customer's tags", description="Replaces the customer's tags; unknown names are created.",
                   request=SetTagsSerializer, responses={200: CustomerTagSerializer(many=True)})
    def put(self, request, pk):
        data = SetTagsSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        tags = services.set_customer_tags(_customer(pk), data.validated_data["tags"])
        return Response(CustomerTagSerializer(tags, many=True).data)


@extend_schema_view(list=extend_schema(tags=TAG, summary="Customer tags (with how many customers have each)"),
                    create=extend_schema(tags=TAG, summary="Create a tag"), destroy=extend_schema(tags=TAG, summary="Delete a tag"))
class CustomerTagViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = CustomerTagSerializer
    pagination_class = None
    queryset = CustomerTag.objects.annotate(customer_count=Count("customers")).order_by("name")


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="Support inbox", description="Filter `status`; `search` name/phone/email/subject/message."),
    retrieve=extend_schema(tags=TAG, summary="Support message"),
    partial_update=extend_schema(tags=TAG, summary="Change a message's status"),
)
class ContactMessageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminContactMessageSerializer
    http_method_names = ["get", "patch", "post", "head", "options"]
    queryset = ContactMessage.objects.select_related("user").prefetch_related("notes__author")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status"]
    search_fields = ["name", "phone", "email", "subject", "message"]

    @extend_schema(tags=TAG, summary="Add a reply/working note", description="Optionally set `status` too; a New message "
                   "moves to In progress.", request=NoteInputSerializer, responses={201: AdminContactMessageSerializer})
    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        message = self.get_object()
        services.add_message_note(message, request.user, request.data.get("text"), status=request.data.get("status"))
        message.refresh_from_db()
        return Response(self.get_serializer(message).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="Abandoned checkouts", description="Checkouts where a name and phone were entered "
                       "but no order followed for CHECKOUT_ABANDON_MINUTES. `status`=dismissed shows dismissed ones; `search`."),
    partial_update=extend_schema(tags=TAG, summary="Dismiss / reopen an abandoned checkout"),
)
class AbandonedCheckoutViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminCheckoutLeadSerializer
    http_method_names = ["get", "patch", "head", "options"]
    filter_backends = [filters.SearchFilter]
    search_fields = ["name", "phone", "email"]

    def get_queryset(self):
        if self.action != "list":
            return CheckoutLead.objects.exclude(status=CheckoutLeadStatus.CONVERTED)  # dismiss / reopen
        if self.request.query_params.get("status") == CheckoutLeadStatus.DISMISSED:
            return CheckoutLead.objects.filter(status=CheckoutLeadStatus.DISMISSED).select_related("user")
        return services.abandoned_checkouts()


@extend_schema_view(
    list=extend_schema(tags=TAG, summary="Return / refund requests", description="Filter `status`; `search` order number/phone/name."),
    retrieve=extend_schema(tags=TAG, summary="Return request"),
    partial_update=extend_schema(tags=TAG, summary="Update a return request", description="`status` (validated transitions) "
                                 "and `admin_note` (shown to the customer)."),
)
class ReturnRequestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAdmin]
    serializer_class = AdminReturnRequestSerializer
    http_method_names = ["get", "patch", "head", "options"]
    queryset = ReturnRequest.objects.select_related("order", "customer", "handled_by")
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["status"]
    search_fields = ["order__number", "customer__phone", "customer__full_name"]

    def perform_update(self, serializer):
        services.update_return_request(
            serializer.instance,
            status=serializer.validated_data.get("status", serializer.instance.status),
            admin_note=serializer.validated_data.get("admin_note", serializer.instance.admin_note),
            user=self.request.user,
        )
