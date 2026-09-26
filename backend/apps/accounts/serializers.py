from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.validators import normalize_bd_phone, validate_image_file

from . import services
from .models import Address, User


class BDPhoneField(serializers.CharField):
    """Accepts 01712345678 / +8801712345678 / 8801712345678 and stores the canonical form."""

    default_error_messages = {"invalid": "Enter a valid Bangladesh mobile number, e.g. 01712345678."}

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_bd_phone(value)
        except DjangoValidationError:
            self.fail("invalid")


# Roles an Admin may assign when managing staff (customers register themselves).
STAFF_ROLE_CHOICES = [(User.Role.CCE.value, User.Role.CCE.label), (User.Role.ADMIN.value, User.Role.ADMIN.label)]


def password_field(**kwargs):
    return serializers.CharField(write_only=True, style={"input_type": "password"}, trim_whitespace=False, **kwargs)


class UniqueContactMixin:
    """Unique-phone / unique-email checks that ignore the instance being updated."""

    def _check_unique(self, field, value):
        queryset = User.objects.filter(**{field: value})
        instance = getattr(self, "instance", None)
        if isinstance(instance, User):
            queryset = queryset.exclude(pk=instance.pk)
        if queryset.exists():
            label = "phone number" if field == "phone" else "email"
            raise serializers.ValidationError(f"A user with this {label} already exists.")
        return value

    def validate_phone(self, value):
        return self._check_unique("phone", value)

    def validate_email(self, value):
        value = (value or "").strip().lower() or None
        return self._check_unique("email", value) if value else None


# --- Users ---------------------------------------------------------------------


class UserSerializer(serializers.ModelSerializer):
    """Compact user shown in auth responses."""

    class Meta:
        model = User
        fields = ["id", "full_name", "phone", "email", "role", "avatar", "must_change_password", "created_via_checkout"]
        read_only_fields = fields


class RegisterSerializer(UniqueContactMixin, serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    phone = BDPhoneField()
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    password = password_field()

    def validate(self, attrs):
        candidate = User(full_name=attrs["full_name"], phone=attrs["phone"], email=attrs.get("email"))
        try:
            validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from None
        return attrs

    def create(self, validated_data):
        return services.register_customer(**validated_data)


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Phone number (any Bangladesh format) or email.")
    password = password_field()


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class AuthResponseSerializer(TokenPairSerializer):
    must_change_password = serializers.BooleanField(
        help_text="True while the account still has a generated password: prompt the user to change it."
    )
    user = UserSerializer()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    old_password = password_field()
    new_password = password_field()

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError({"new_password": ["The new password must be different."]})
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from None
        return attrs


class PasswordChangedResponseSerializer(TokenPairSerializer):
    detail = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Phone number or email of the account.")


class ResetPasswordSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = password_field()

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from None
        return value


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


# --- Profile & address book ------------------------------------------------------


class ProfileSerializer(UniqueContactMixin, serializers.ModelSerializer):
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    avatar = serializers.ImageField(required=False, allow_null=True, validators=[validate_image_file])

    class Meta:
        model = User
        fields = [
            "id", "full_name", "phone", "email", "avatar", "role",
            "must_change_password", "created_via_checkout", "created_at",
        ]
        # The phone is the login identifier, so changing it is an admin/support action.
        read_only_fields = ["id", "phone", "role", "must_change_password", "created_via_checkout", "created_at"]


class AddressSerializer(serializers.ModelSerializer):
    phone = BDPhoneField()

    class Meta:
        model = Address
        fields = [
            "id", "label", "full_name", "phone", "division", "district", "area",
            "address_line", "postal_code", "is_default", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_is_default(self, value):
        if self.instance and self.instance.is_default and not value:
            raise serializers.ValidationError("Set another address as the default instead.")
        return value

    def create(self, validated_data):
        return services.create_address(self.context["request"].user, **validated_data)

    def update(self, instance, validated_data):
        return services.update_address(instance, **validated_data)


# --- Admin: staff ----------------------------------------------------------------


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "full_name", "phone", "email", "role", "is_active", "avatar", "last_login", "created_at"]
        read_only_fields = fields


class StaffCreateSerializer(UniqueContactMixin, serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    phone = BDPhoneField()
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    role = serializers.ChoiceField(choices=STAFF_ROLE_CHOICES, default=User.Role.CCE)
    password = password_field()

    def validate(self, attrs):
        candidate = User(full_name=attrs["full_name"], phone=attrs["phone"], email=attrs.get("email"))
        try:
            validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from None
        return attrs

    def create(self, validated_data):
        return services.create_staff(**validated_data)


class StaffUpdateSerializer(UniqueContactMixin, serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=False)
    phone = BDPhoneField(required=False)
    email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)
    role = serializers.ChoiceField(choices=STAFF_ROLE_CHOICES, required=False)
    password = password_field(required=False)

    def validate_password(self, value):
        try:
            validate_password(value, self.instance)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from None
        return value

    def update(self, instance, validated_data):
        return services.update_staff(instance, self.context["request"].user, **validated_data)


# --- Admin: customers --------------------------------------------------------------


class CustomerListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "full_name", "phone", "email", "is_active", "created_via_checkout",
            "must_change_password", "last_login", "created_at",
        ]
        read_only_fields = fields


class CustomerDetailSerializer(CustomerListSerializer):
    avatar = serializers.ImageField(read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)

    class Meta(CustomerListSerializer.Meta):
        fields = [*CustomerListSerializer.Meta.fields, "avatar", "addresses"]
        read_only_fields = fields


# --- Admin: all users (User Management) --------------------------------------------------


class AdminUserSerializer(serializers.ModelSerializer):
    """A user as User Management shows it. Never includes the password or its hash."""

    class Meta:
        model = User
        fields = [
            "id", "avatar", "phone", "full_name", "email", "role", "is_active", "created_via_checkout",
            "must_change_password", "last_login", "created_at",
        ]
        read_only_fields = fields  # created_at / last_login are display-only; last_login is set by services.record_login


def _check_password(password, confirm, candidate):
    """Confirmation first, then Django's AUTH_PASSWORD_VALIDATORS (similarity, length, common, numeric)."""
    if password != confirm:
        raise serializers.ValidationError({"password_confirm": ["Passwords do not match."]})
    try:
        validate_password(password, candidate)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)}) from None


class AdminUserCreateSerializer(UniqueContactMixin, serializers.Serializer):
    phone = BDPhoneField()
    full_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.CUSTOMER)
    avatar = serializers.ImageField(required=False, allow_null=True, validators=[validate_image_file])
    password = password_field()
    password_confirm = password_field()

    def validate_full_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Full name is required.")
        return value

    def validate(self, attrs):
        _check_password(attrs["password"], attrs["password_confirm"], User(full_name=attrs["full_name"], phone=attrs["phone"]))
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return services.create_user_by_admin(**validated_data)


class AdminUserUpdateSerializer(UniqueContactMixin, serializers.Serializer):
    """Partial update. Leave `password` (and its confirmation) empty to keep the current password."""

    phone = BDPhoneField(required=False)
    full_name = serializers.CharField(max_length=150, required=False)
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)
    avatar = serializers.ImageField(required=False, allow_null=True, validators=[validate_image_file], help_text="Send empty/null to remove.")
    password = password_field(required=False, allow_blank=True)
    password_confirm = password_field(required=False, allow_blank=True)
    must_change_password = serializers.BooleanField(
        required=False, help_text="With a new password: true makes it temporary (the user must change it at next login)."
    )

    def validate_full_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Full name is required.")
        return value

    def validate(self, attrs):
        password = attrs.pop("password", "") or ""
        confirm = attrs.pop("password_confirm", "") or ""
        if password or confirm:
            candidate = User(
                pk=self.instance.pk, full_name=attrs.get("full_name", self.instance.full_name),
                phone=attrs.get("phone", self.instance.phone), email=self.instance.email,
            )
            _check_password(password, confirm, candidate)
            attrs["password"] = password
        return attrs

    def update(self, instance, validated_data):
        try:
            return services.update_user_by_admin(instance, self.context["request"].user, **validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"non_field_errors": list(exc.messages)}) from None
