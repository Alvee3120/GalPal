"""Accounts business logic. Views and serializers stay thin and call in here."""

import logging
import secrets
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.messaging import send_sms
from apps.core.validators import normalize_bd_phone

from .exceptions import AccountAlreadyExists, AccountDisabled, InvalidCredentials, InvalidOTP
from .models import Address, PasswordResetOTP, User

logger = logging.getLogger(__name__)


# --- Tokens & authentication --------------------------------------------------


def authenticate(identifier, password):
    """
    Check phone-or-email + password. Returns the user.

    Wrong identifier and wrong password are indistinguishable. A deactivated account is
    only reported after the password was right, so this can't be used to probe accounts.
    """
    user = User.objects.get_by_identifier(identifier)
    if user is None:
        # Burn comparable time so timing doesn't reveal whether the account exists.
        User().set_password(password)
        raise InvalidCredentials()
    if not user.check_password(password):
        raise InvalidCredentials()
    if not user.is_active:
        raise AccountDisabled()
    return user


def issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def revoke_refresh_tokens(user):
    """Blacklist every outstanding refresh token of the user (all devices logged out)."""
    tokens = OutstandingToken.objects.filter(user=user, blacklistedtoken__isnull=True)
    BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in tokens], ignore_conflicts=True
    )


def record_login(user):
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])


# --- Registration & passwords -------------------------------------------------


def register_customer(*, full_name, phone, email=None, password):
    return User.objects.create_user(
        phone=phone, full_name=full_name, email=email, password=password, role=User.Role.CUSTOMER
    )


def change_password(user, new_password):
    """Set a new password, clear `must_change_password`, log out other devices, return new tokens."""
    with transaction.atomic():
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password", "updated_at"])
        revoke_refresh_tokens(user)
    return issue_tokens(user)


def _otp_hash(user, code):
    return salted_hmac(
        "galpal.password_reset_otp", f"{user.pk}:{code}", algorithm="sha256"
    ).hexdigest()


def request_password_reset(identifier):
    """
    Send a one-time reset code to the account behind `identifier` (email or phone).

    Always returns None and never reveals whether the account exists. Delivery goes through
    the pluggable email / SMS backends; failures are logged (without the code) and swallowed.
    """
    identifier = (identifier or "").strip()
    user = User.objects.get_by_identifier(identifier)
    if user is None or not user.is_active:
        return

    now = timezone.now()
    cooldown = timedelta(seconds=settings.PASSWORD_RESET_OTP_RESEND_COOLDOWN_SECONDS)
    if user.password_reset_otps.filter(created_at__gt=now - cooldown).exists():
        return  # too soon after the last code: silently skip (anti SMS/email bombing)

    code = f"{secrets.randbelow(10**6):06d}"
    with transaction.atomic():
        user.password_reset_otps.filter(used_at__isnull=True).update(used_at=now)
        PasswordResetOTP.objects.create(
            user=user,
            code_hash=_otp_hash(user, code),
            expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_OTP_TTL_MINUTES),
        )

    message = (
        f"Your GalPal password reset code is {code}. "
        f"It expires in {settings.PASSWORD_RESET_OTP_TTL_MINUTES} minutes. Do not share it."
    )
    try:
        if "@" in identifier:
            send_mail("Your GalPal password reset code", message, None, [user.email])
        else:
            send_sms(user.phone, message)
    except Exception:  # noqa: BLE001 - delivery problems must not change the response
        logger.exception("Could not deliver password reset code to user %s", user.pk)


def reset_password(identifier, code, new_password):
    """Consume a valid reset code and set the new password. Every failure looks the same."""
    user = User.objects.get_by_identifier(identifier)
    if user is None or not user.is_active:
        raise InvalidOTP()

    valid = False
    with transaction.atomic():
        otp = (
            PasswordResetOTP.objects.select_for_update()
            .filter(user=user, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if otp and not otp.is_expired and otp.attempts < settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS:
            if constant_time_compare(otp.code_hash, _otp_hash(user, str(code).strip())):
                valid = True
                otp.used_at = timezone.now()
                otp.save(update_fields=["used_at", "updated_at"])
                user.set_password(new_password)
                user.must_change_password = False
                user.save(update_fields=["password", "must_change_password", "updated_at"])
                revoke_refresh_tokens(user)
            else:
                otp.attempts += 1
                otp.save(update_fields=["attempts", "updated_at"])
    # Raise outside the atomic block so the failed-attempt counter is committed.
    if not valid:
        raise InvalidOTP()


# --- Address book -------------------------------------------------------------


def _lock_user(user):
    """Serialise address changes per user so the one-default rule can't be raced."""
    User.objects.select_for_update().only("id").get(pk=user.pk)


@transaction.atomic
def create_address(user, *, is_default=False, **fields):
    _lock_user(user)
    if not user.addresses.exists():
        is_default = True  # the first address is always the default
    if is_default:
        user.addresses.filter(is_default=True).update(is_default=False)
    address = Address(user=user, is_default=is_default, **fields)
    address.full_clean(exclude=["user"])
    address.save()
    return address


@transaction.atomic
def update_address(address, **fields):
    _lock_user(address.user)
    if fields.get("is_default"):
        address.user.addresses.filter(is_default=True).exclude(pk=address.pk).update(is_default=False)
    for name, value in fields.items():
        setattr(address, name, value)
    address.save()
    return address


@transaction.atomic
def set_default_address(address):
    return update_address(address, is_default=True)


@transaction.atomic
def delete_address(address):
    _lock_user(address.user)
    was_default = address.is_default
    user = address.user
    address.delete()
    if was_default:
        replacement = user.addresses.order_by("-created_at").first()
        if replacement:
            replacement.is_default = True
            replacement.save(update_fields=["is_default", "updated_at"])


# --- Checkout-created accounts (used by Module 10) ----------------------------

_LOWER, _UPPER, _DIGITS = "abcdefghjkmnpqrstuvwxyz", "ABCDEFGHJKMNPQRSTUVWXYZ", "23456789"  # no look-alikes


def generate_password(length=14):
    """A random password (>= 12 chars) with lower, upper and digits, from the `secrets` module."""
    length = max(length, 12)
    chars = [secrets.choice(_LOWER), secrets.choice(_UPPER), secrets.choice(_DIGITS)]
    pool = _LOWER + _UPPER + _DIGITS
    chars += [secrets.choice(pool) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


@dataclass(frozen=True)
class NewAccount:
    """Result of `create_customer_account`. Unpackable as `user, password = ...`."""

    user: User
    # repr=False keeps the one-time password out of logs, tracebacks and debuggers' repr.
    password: str = field(repr=False)

    def __iter__(self):
        return iter((self.user, self.password))


def create_customer_account(name, phone, email, address=None, source="checkout"):
    """
    Create a customer account with a generated password and return `(user, plain_password)`.

    * Only the password hash is stored; the plain password is returned exactly once, for the
      caller to deliver (e.g. by email). It is never logged, stored or put in an API response.
    * `source="checkout"` sets `created_via_checkout`. The account always gets
      `must_change_password=True` because the customer doesn't know the password.
    * `address` (dict with district, address_line and optionally full_name, phone, division,
      area, postal_code, label) is saved as the user's default address.
    * Raises `AccountAlreadyExists` if the phone or email is taken. Callers must NOT reveal that
      to end users. Runs atomically: on any failure nothing is created.
    * `ValidationError` for an invalid phone/email/address.
    """
    phone = normalize_bd_phone(phone)
    email = (email or "").strip().lower() or None
    password = generate_password()

    try:
        with transaction.atomic():
            if User.objects.filter(phone=phone).exists():
                raise AccountAlreadyExists("phone")
            if email and User.objects.filter(email=email).exists():
                raise AccountAlreadyExists("email")

            user = User.objects.create_user(
                phone=phone,
                full_name=name,
                email=email,
                password=password,
                created_via_checkout=(source == "checkout"),
                must_change_password=True,
            )
            if address:
                fields = {"label": "Home", "full_name": name, "phone": phone, **address}
                fields["phone"] = normalize_bd_phone(fields["phone"])
                create_address(user, is_default=True, **fields)
    except IntegrityError:  # lost a race with a concurrent signup for the same phone/email
        raise AccountAlreadyExists("phone or email") from None
    return NewAccount(user=user, password=password)


# --- Admin: staff & customer management ---------------------------------------


def _ensure_another_active_admin(user):
    """Refuse changes that would leave the system without an active Admin."""
    if not (user.is_admin and user.is_active):
        return
    others = list(
        User.objects.select_for_update()
        .filter(role=User.Role.ADMIN, is_active=True)
        .exclude(pk=user.pk)
        .values_list("pk", flat=True)
    )
    if not others:
        raise ValidationError("There must be at least one active administrator.", code="last_admin")


@transaction.atomic
def create_staff(*, full_name, phone, password, role, email=None):
    return User.objects.create_user(
        phone=phone, full_name=full_name, email=email, password=password, role=role
    )


@transaction.atomic
def update_staff(user, actor, *, password=None, **fields):
    if "role" in fields and fields["role"] != user.role:
        if user.pk == actor.pk:
            raise ValidationError("You cannot change your own role.", code="self_role_change")
        _ensure_another_active_admin(user)
    for name, value in fields.items():
        setattr(user, name, value)
    if password:
        user.set_password(password)
        user.must_change_password = False
        revoke_refresh_tokens(user)
    user.save()
    return user


@transaction.atomic
def set_user_active(user, actor, active):
    if not active:
        if user.pk == actor.pk:
            raise ValidationError("You cannot deactivate your own account.", code="self_deactivate")
        _ensure_another_active_admin(user)
    user.is_active = active
    user.save(update_fields=["is_active", "updated_at"])
    if not active:
        revoke_refresh_tokens(user)
    return user


@transaction.atomic
def delete_staff(user, actor):
    if user.pk == actor.pk:
        raise ValidationError("You cannot delete your own account.", code="self_delete")
    _ensure_another_active_admin(user)
    user.delete()
