import logging

from django.utils.decorators import method_decorator
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.serializers import ErrorResponseSerializer

from . import services
from .filters import CustomerFilter, StaffFilter, UserFilter
from .models import Address, User
from .permissions import IsAdmin, IsOwner
from .serializers import (
    AddressSerializer,
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    AuthResponseSerializer,
    ChangePasswordSerializer,
    CustomerDetailSerializer,
    CustomerListSerializer,
    DetailSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangedResponseSerializer,
    ProfileSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    StaffCreateSerializer,
    StaffSerializer,
    StaffUpdateSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)

ERR = ErrorResponseSerializer
AUTH_ERRORS = {
    400: OpenApiResponse(ERR, description="Validation error"),
    401: OpenApiResponse(ERR, description="Not authenticated / invalid credentials"),
    403: OpenApiResponse(ERR, description="Permission denied"),
}


def auth_payload(user, request):
    _merge_guest_cart(request, user)
    return {
        **services.issue_tokens(user),
        "must_change_password": user.must_change_password,
        "user": UserSerializer(user, context={"request": request}).data,
    }


def _merge_guest_cart(request, user):
    """Fold a guest's cart (Module 7) into their account right after login/registration."""
    from apps.cart.services import merge_guest_cart_into_user, token_from_request

    token = token_from_request(request)
    if token is None:
        return
    try:
        merge_guest_cart_into_user(token, user)
    except Exception:  # noqa: BLE001 - a cart merge problem must never block login
        logger.warning("Could not merge guest cart into user %s", user.pk, exc_info=True)


# --- Authentication -------------------------------------------------------------------


class _PublicAPIView(APIView):
    authentication_classes = []  # a stale/invalid Authorization header must not break these
    permission_classes = [AllowAny]


class RegisterView(_PublicAPIView):
    @extend_schema(
        tags=["Auth"], summary="Register a customer account",
        description="Creates a customer account and logs the user in (returns JWT tokens).",
        request=RegisterSerializer,
        responses={201: AuthResponseSerializer, 400: OpenApiResponse(ERR, description="Validation error")},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        services.record_login(user)
        return Response(auth_payload(user, request), status=status.HTTP_201_CREATED)


class LoginView(_PublicAPIView):
    @extend_schema(
        tags=["Auth"], summary="Login with phone or email + password",
        description=(
            "`identifier` may be a phone number (`01712345678`, `+8801712345678`) or an email.\n\n"
            "`must_change_password` is true for accounts created at checkout with a generated password: "
            "the frontend should send the user to the change-password screen."
        ),
        request=LoginSerializer,
        responses={200: AuthResponseSerializer, **AUTH_ERRORS},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.authenticate(**serializer.validated_data)
        services.record_login(user)
        return Response(auth_payload(user, request))


class LogoutView(_PublicAPIView):
    @extend_schema(
        tags=["Auth"], summary="Logout (blacklist the refresh token)",
        request=LogoutSerializer,
        responses={204: None, 400: OpenApiResponse(ERR, description="Invalid or already-used refresh token")},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            raise ValidationError({"refresh": ["Token is invalid or expired."]}) from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Auth"], summary="Change password",
        description="Clears `must_change_password`, logs out every other device and returns a fresh token pair.",
        request=ChangePasswordSerializer,
        responses={200: PasswordChangedResponseSerializer, 400: OpenApiResponse(ERR), 401: OpenApiResponse(ERR)},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        tokens = services.change_password(request.user, serializer.validated_data["new_password"])
        return Response({"detail": "Password changed.", **tokens})


class ForgotPasswordView(_PublicAPIView):
    @extend_schema(
        tags=["Auth"], summary="Request a password reset code",
        description=(
            "Sends a 6-digit one-time code by SMS (phone identifier) or email (email identifier). "
            "The response is always the same, whether or not the account exists."
        ),
        request=ForgotPasswordSerializer,
        responses={200: DetailSerializer},
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_password_reset(serializer.validated_data["identifier"])
        return Response({"detail": "If an account exists, a reset code has been sent."})


class ResetPasswordView(_PublicAPIView):
    @extend_schema(
        tags=["Auth"], summary="Reset password with the one-time code",
        request=ResetPasswordSerializer,
        responses={200: DetailSerializer, 400: OpenApiResponse(ERR, description="Invalid/expired code or weak password")},
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        services.reset_password(data["identifier"], data["otp"], data["new_password"])
        return Response({"detail": "Password has been reset. You can now log in."})


# --- Profile & address book -------------------------------------------------------------


@extend_schema_view(
    get=extend_schema(tags=["Account"], summary="Get my profile"),
    patch=extend_schema(tags=["Account"], summary="Update my profile (name, email, avatar)"),
)
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user


@extend_schema_view(
    list=extend_schema(tags=["Account"], summary="List my saved addresses"),
    retrieve=extend_schema(tags=["Account"], summary="Get one of my addresses"),
    create=extend_schema(tags=["Account"], summary="Add an address (the first one becomes the default)"),
    partial_update=extend_schema(tags=["Account"], summary="Update an address"),
    destroy=extend_schema(tags=["Account"], summary="Delete an address (the newest remaining becomes default)"),
)
class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated, IsOwner]
    owner_field = "user"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation has no real user
            return Address.objects.none()
        return Address.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        services.delete_address(instance)

    @extend_schema(tags=["Account"], summary="Make this my default address", request=None, responses=AddressSerializer)
    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        address = services.set_default_address(self.get_object())
        return Response(self.get_serializer(address).data)


# --- Admin: staff -----------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(tags=["Admin – Staff"], summary="List staff (Admin and CCE accounts)"),
    retrieve=extend_schema(tags=["Admin – Staff"], summary="Get a staff account"),
    create=extend_schema(
        tags=["Admin – Staff"], summary="Create a staff account (e.g. a CCE)",
        request=StaffCreateSerializer, responses={201: StaffSerializer},
    ),
    partial_update=extend_schema(
        tags=["Admin – Staff"], summary="Update a staff account",
        request=StaffUpdateSerializer, responses={200: StaffSerializer},
    ),
    destroy=extend_schema(
        tags=["Admin – Staff"], summary="Delete a staff account",
        description="Prefer deactivating. Cannot delete yourself or the last active admin.",
    ),
)
class StaffViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    filterset_class = StaffFilter
    ordering_fields = ["created_at", "full_name", "last_login"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return User.objects.filter(role__in=[User.Role.ADMIN, User.Role.CCE])

    def get_serializer_class(self):
        return {"create": StaffCreateSerializer, "partial_update": StaffUpdateSerializer}.get(
            self.action, StaffSerializer
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(StaffSerializer(user, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(StaffSerializer(user, context={"request": request}).data)

    def perform_destroy(self, instance):
        services.delete_staff(instance, self.request.user)

    @extend_schema(tags=["Admin – Staff"], summary="Activate a staff account", request=None, responses=StaffSerializer)
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = services.set_user_active(self.get_object(), request.user, True)
        return Response(StaffSerializer(user, context={"request": request}).data)

    @extend_schema(
        tags=["Admin – Staff"], summary="Deactivate a staff account",
        description="Blocks login immediately and revokes refresh tokens. Cannot deactivate yourself or the last active admin.",
        request=None, responses=StaffSerializer,
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = services.set_user_active(self.get_object(), request.user, False)
        return Response(StaffSerializer(user, context={"request": request}).data)


# --- Admin: customers ---------------------------------------------------------------------


@extend_schema_view(
    list=extend_schema(tags=["Admin – Customers"], summary="List customers (search, filter, order)"),
    retrieve=extend_schema(tags=["Admin – Customers"], summary="Customer detail with address book"),
)
class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdmin]
    filterset_class = CustomerFilter
    ordering_fields = ["created_at", "full_name", "last_login"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return User.objects.filter(role=User.Role.CUSTOMER).prefetch_related("addresses")

    def get_serializer_class(self):
        return CustomerDetailSerializer if self.action == "retrieve" else CustomerListSerializer

    @extend_schema(tags=["Admin – Customers"], summary="Activate a customer", request=None, responses=CustomerDetailSerializer)
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = services.set_user_active(self.get_object(), request.user, True)
        return Response(CustomerDetailSerializer(user, context={"request": request}).data)

    @extend_schema(
        tags=["Admin – Customers"], summary="Deactivate a customer",
        description="The customer can no longer log in; their refresh tokens are revoked.",
        request=None, responses=CustomerDetailSerializer,
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = services.set_user_active(self.get_object(), request.user, False)
        return Response(CustomerDetailSerializer(user, context={"request": request}).data)


# --- Admin: all users (User Management) --------------------------------------------------------


@extend_schema_view(
    list=extend_schema(
        tags=["Admin – Users"], summary="List users (every role)",
        description="`search` (name, phone in any format, email), `role`, `is_active`, `created_via_checkout`. Paginated.",
    ),
    retrieve=extend_schema(tags=["Admin – Users"], summary="Get a user"),
    create=extend_schema(
        tags=["Admin – Users"], summary="Create a user (any role)",
        description="Password is checked against AUTH_PASSWORD_VALIDATORS and must match `password_confirm`.",
        request=AdminUserCreateSerializer, responses={201: AdminUserSerializer},
    ),
    partial_update=extend_schema(
        tags=["Admin – Users"], summary="Update a user",
        description=(
            "Phone, name, role, is_active, and optionally a new password (+ confirmation; leave both empty to keep it). "
            "You can't change your own role or deactivate yourself, and there must always be an active Admin."
        ),
        request=AdminUserUpdateSerializer, responses={200: AdminUserSerializer},
    ),
    destroy=extend_schema(
        tags=["Admin – Users"], summary="Delete a user",
        description="Not yourself, not the last active Admin. Their orders and reviews stay (the link to the account is cleared).",
    ),
)
class UserViewSet(viewsets.ModelViewSet):
    """User Management: every account, any role. Admin only. Reuses the staff/customer rules in `services`."""

    permission_classes = [IsAdmin]
    queryset = User.objects.all()
    filterset_class = UserFilter
    ordering_fields = ["created_at", "full_name", "phone", "last_login"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        return {"create": AdminUserCreateSerializer, "partial_update": AdminUserUpdateSerializer}.get(self.action, AdminUserSerializer)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(AdminUserSerializer(user, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(AdminUserSerializer(user, context={"request": request}).data)

    def perform_destroy(self, instance):
        services.delete_user(instance, self.request.user)
