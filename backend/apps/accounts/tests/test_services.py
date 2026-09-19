import logging
import re
from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import services
from apps.accounts.exceptions import AccountAlreadyExists, AccountDisabled, InvalidCredentials, InvalidOTP
from apps.accounts.models import Address, PasswordResetOTP, User
from apps.core.messaging import LocMemSMSBackend

from .factories import AddressFactory, AdminFactory, CCEFactory, UserFactory

pytestmark = pytest.mark.django_db

ADDRESS = {"district": "Dhaka", "address_line": "House 5, Road 3", "area": "Mirpur", "division": "Dhaka"}


# --- create_customer_account -------------------------------------------------------------


def test_create_customer_account_returns_user_and_one_time_password():
    user, password = services.create_customer_account("Rina Akter", "+8801712345678", "Rina@Example.com", ADDRESS)
    assert user.pk and user.phone == "01712345678" and user.email == "rina@example.com"
    assert user.role == User.Role.CUSTOMER
    assert user.created_via_checkout is True and user.must_change_password is True
    assert user.check_password(password)


def test_generated_password_is_strong_random_and_only_hash_is_stored():
    passwords = set()
    for i in range(20):
        user, password = services.create_customer_account(f"U{i}", f"0171000{i:04d}", None)
        passwords.add(password)
        assert len(password) >= 12
        assert re.search(r"[a-z]", password) and re.search(r"[A-Z]", password) and re.search(r"\d", password)
        assert user.password != password and password not in user.password
    assert len(passwords) == 20


def test_generate_password_minimum_length_and_uses_secrets():
    assert len(services.generate_password(4)) == 12  # never below 12
    with mock.patch("apps.accounts.services.secrets.choice", wraps=__import__("secrets").choice) as choice:
        services.generate_password()
    assert choice.called


def test_password_never_appears_in_repr_or_logs(caplog):
    caplog.set_level(logging.DEBUG)
    result = services.create_customer_account("Rina", "01712345678", None, ADDRESS)
    assert result.password not in repr(result)
    assert result.password not in str(result)
    assert result.password not in caplog.text
    user, password = result  # still unpackable
    assert user is result.user and password == result.password


def test_password_is_not_stored_anywhere_in_the_database():
    user, password = services.create_customer_account("Rina", "01712345678", "rina@example.com", ADDRESS)
    row = User.objects.filter(pk=user.pk).values().get()
    assert not any(password == v or (isinstance(v, str) and password in v) for v in row.values())


def test_address_is_saved_as_default_with_sensible_fallbacks():
    user, _ = services.create_customer_account("Rina Akter", "01712345678", None, ADDRESS)
    address = user.addresses.get()
    assert address.is_default and address.label == "Home"
    assert address.full_name == "Rina Akter" and address.phone == "01712345678"
    assert address.district == "Dhaka" and address.area == "Mirpur"


def test_account_without_address_or_email_is_fine():
    user, _ = services.create_customer_account("Rina", "01712345678", "", None)
    assert user.email is None and user.addresses.count() == 0


def test_source_other_than_checkout_does_not_flag_checkout():
    user, _ = services.create_customer_account("Rina", "01712345678", None, source="import")
    assert user.created_via_checkout is False and user.must_change_password is True


def test_duplicate_phone_or_email_raises_and_creates_nothing():
    existing = UserFactory(phone="01712345678", email="taken@example.com")
    with pytest.raises(AccountAlreadyExists) as exc:
        services.create_customer_account("X", "+8801712345678", None, ADDRESS)
    assert exc.value.field == "phone"
    with pytest.raises(AccountAlreadyExists) as exc:
        services.create_customer_account("X", "01812345678", "TAKEN@example.com", ADDRESS)
    assert exc.value.field == "email"
    assert User.objects.count() == 1 and Address.objects.count() == 0 and User.objects.get() == existing


def test_invalid_input_is_a_validation_error():
    with pytest.raises(ValidationError):
        services.create_customer_account("X", "12345", None)


def test_bad_address_rolls_back_the_whole_account():
    with pytest.raises(ValidationError):
        services.create_customer_account("X", "01712345678", None, {"district": "", "address_line": ""})
    assert User.objects.count() == 0 and Address.objects.count() == 0


def test_rolls_back_inside_an_outer_transaction_savepoint():
    """Module 10 wraps this in the order transaction; a failure must not poison it."""
    with transaction.atomic():
        with pytest.raises(ValidationError):
            services.create_customer_account("X", "01712345678", None, {"district": "", "address_line": ""})
        User.objects.create_user(phone="01812345678", full_name="ok")  # outer transaction still usable
    assert User.objects.count() == 1


# --- authenticate / tokens -----------------------------------------------------------------


def test_authenticate_by_phone_and_email(password):
    user = UserFactory(phone="01712345678", email="a@example.com")
    assert services.authenticate("01712345678", password) == user
    assert services.authenticate("+8801712345678", password) == user
    assert services.authenticate("A@example.com", password) == user


@pytest.mark.parametrize("identifier", ["01712345678", "nobody@example.com", "garbage", ""])
def test_authenticate_fails_identically_for_unknown_or_wrong(identifier):
    UserFactory(phone="01712345678")
    with pytest.raises(InvalidCredentials):
        services.authenticate(identifier, "wrong-password")


def test_authenticate_reports_disabled_only_after_correct_password(password):
    UserFactory(phone="01712345678", is_active=False)
    with pytest.raises(InvalidCredentials):
        services.authenticate("01712345678", "wrong")
    with pytest.raises(AccountDisabled):
        services.authenticate("01712345678", password)


def test_revoke_refresh_tokens_blacklists_all_outstanding():
    user, other = UserFactory(), UserFactory()
    for _ in range(3):
        RefreshToken.for_user(user)
    keep = RefreshToken.for_user(other)
    services.revoke_refresh_tokens(user)
    services.revoke_refresh_tokens(user)  # idempotent
    assert BlacklistedToken.objects.count() == 3
    assert not BlacklistedToken.objects.filter(token__user=other).exists()
    RefreshToken(str(keep))  # other user's token still valid


# --- change password -------------------------------------------------------------------------


def test_change_password_clears_flag_revokes_old_tokens_and_returns_new_pair():
    user = UserFactory(must_change_password=True)
    old_refresh = str(RefreshToken.for_user(user))
    tokens = services.change_password(user, "An0ther!Str0ngPass")
    user.refresh_from_db()
    assert user.check_password("An0ther!Str0ngPass") and user.must_change_password is False
    with pytest.raises(Exception):
        RefreshToken(old_refresh)
    RefreshToken(tokens["refresh"])  # the new one works


# --- password reset OTP ----------------------------------------------------------------------


def last_sms_code():
    return re.search(r"\b(\d{6})\b", LocMemSMSBackend.outbox[-1]["message"]).group(1)


def test_request_reset_by_phone_sends_sms_and_stores_only_a_hash():
    user = UserFactory(phone="01712345678")
    services.request_password_reset("+8801712345678")
    assert len(LocMemSMSBackend.outbox) == 1 and LocMemSMSBackend.outbox[0]["to"] == "01712345678"
    code = last_sms_code()
    otp = PasswordResetOTP.objects.get(user=user)
    assert otp.code_hash != code and len(otp.code_hash) == 64
    assert otp.code_hash == services._otp_hash(user, code)
    assert otp.expires_at > timezone.now() and otp.attempts == 0


def test_request_reset_by_email_sends_email_not_sms():
    UserFactory(email="rina@example.com")
    services.request_password_reset("Rina@example.com")
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["rina@example.com"]
    assert not LocMemSMSBackend.outbox
    assert re.search(r"\b\d{6}\b", mail.outbox[0].body)


def test_request_reset_is_silent_for_unknown_or_inactive_accounts():
    UserFactory(phone="01712345678", is_active=False)
    for identifier in ["01712345678", "01899999999", "nobody@example.com", "garbage", ""]:
        assert services.request_password_reset(identifier) is None
    assert not LocMemSMSBackend.outbox and not mail.outbox and not PasswordResetOTP.objects.exists()


def test_resend_cooldown_blocks_rapid_repeat_requests(settings):
    UserFactory(phone="01712345678")
    services.request_password_reset("01712345678")
    services.request_password_reset("01712345678")
    assert len(LocMemSMSBackend.outbox) == 1
    settings.PASSWORD_RESET_OTP_RESEND_COOLDOWN_SECONDS = 0
    services.request_password_reset("01712345678")
    assert len(LocMemSMSBackend.outbox) == 2


def test_new_code_invalidates_the_previous_one(settings):
    settings.PASSWORD_RESET_OTP_RESEND_COOLDOWN_SECONDS = 0
    UserFactory(phone="01712345678")
    with mock.patch("apps.accounts.services.secrets.randbelow", side_effect=[111111, 222222]):
        services.request_password_reset("01712345678")
        services.request_password_reset("01712345678")
    assert "111111" in LocMemSMSBackend.outbox[0]["message"]
    assert "222222" in LocMemSMSBackend.outbox[1]["message"]
    with pytest.raises(InvalidOTP):
        services.reset_password("01712345678", "111111", "N3w!Str0ngPassw0rd")
    services.reset_password("01712345678", "222222", "N3w!Str0ngPassw0rd")


def test_delivery_failure_is_swallowed_and_never_logs_the_code(caplog):
    UserFactory(phone="01712345678")
    with mock.patch("apps.accounts.services.send_sms", side_effect=RuntimeError("provider down")):
        services.request_password_reset("01712345678")  # must not raise
    assert "Could not deliver" in caplog.text
    assert not re.search(r"\b\d{6}\b", caplog.text.replace("user 1", ""))


def test_reset_password_success_sets_password_and_revokes_sessions():
    user = UserFactory(phone="01712345678", must_change_password=True)
    refresh = str(RefreshToken.for_user(user))
    services.request_password_reset("01712345678")
    services.reset_password("01712345678", last_sms_code(), "N3w!Str0ngPassw0rd")
    user.refresh_from_db()
    assert user.check_password("N3w!Str0ngPassw0rd") and user.must_change_password is False
    with pytest.raises(Exception):
        RefreshToken(refresh)


def test_code_is_single_use():
    UserFactory(phone="01712345678")
    services.request_password_reset("01712345678")
    code = last_sms_code()
    services.reset_password("01712345678", code, "N3w!Str0ngPassw0rd")
    with pytest.raises(InvalidOTP):
        services.reset_password("01712345678", code, "Y3t!An0therPassw0rd")


def test_wrong_code_counts_attempts_then_locks_out_even_the_right_code(settings):
    user = UserFactory(phone="01712345678")
    services.request_password_reset("01712345678")
    code = last_sms_code()
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS):
        with pytest.raises(InvalidOTP):
            services.reset_password("01712345678", wrong, "N3w!Str0ngPassw0rd")
    assert PasswordResetOTP.objects.get(user=user).attempts == settings.PASSWORD_RESET_OTP_MAX_ATTEMPTS
    with pytest.raises(InvalidOTP):
        services.reset_password("01712345678", code, "N3w!Str0ngPassw0rd")  # locked
    user.refresh_from_db()
    assert not user.check_password("N3w!Str0ngPassw0rd")


def test_expired_code_is_rejected():
    UserFactory(phone="01712345678")
    services.request_password_reset("01712345678")
    PasswordResetOTP.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(InvalidOTP):
        services.reset_password("01712345678", last_sms_code(), "N3w!Str0ngPassw0rd")


def test_reset_for_unknown_user_looks_like_any_other_failure():
    with pytest.raises(InvalidOTP):
        services.reset_password("01899999999", "123456", "N3w!Str0ngPassw0rd")


def test_code_for_one_user_does_not_work_for_another():
    UserFactory(phone="01712345678")
    other = UserFactory(phone="01812345678")
    services.request_password_reset("01712345678")
    with pytest.raises(InvalidOTP):
        services.reset_password("01812345678", last_sms_code(), "N3w!Str0ngPassw0rd")
    other.refresh_from_db()
    assert not other.check_password("N3w!Str0ngPassw0rd")


# --- address book ------------------------------------------------------------------------------

FIELDS = {"full_name": "R", "phone": "01812345678", "district": "Dhaka", "address_line": "Somewhere 1"}


def test_first_address_becomes_default():
    user = UserFactory()
    assert services.create_address(user, **FIELDS).is_default is True
    assert services.create_address(user, **FIELDS).is_default is False


def test_new_default_replaces_the_old_one():
    user = UserFactory()
    first = services.create_address(user, **FIELDS)
    second = services.create_address(user, is_default=True, **FIELDS)
    first.refresh_from_db()
    assert not first.is_default and second.is_default
    assert user.addresses.filter(is_default=True).count() == 1


def test_set_default_and_users_are_isolated():
    a, b = UserFactory(), UserFactory()
    a1, a2 = services.create_address(a, **FIELDS), services.create_address(a, **FIELDS)
    b1 = services.create_address(b, **FIELDS)
    services.set_default_address(a2)
    a1.refresh_from_db(); b1.refresh_from_db()
    assert a2.is_default and not a1.is_default and b1.is_default


def test_deleting_default_promotes_newest_remaining():
    user = UserFactory()
    a1 = services.create_address(user, **FIELDS)
    a2 = services.create_address(user, **FIELDS)
    a3 = services.create_address(user, **FIELDS)
    services.delete_address(a1)
    a2.refresh_from_db(); a3.refresh_from_db()
    assert a3.is_default and not a2.is_default
    services.delete_address(a3); services.delete_address(a2)
    assert not user.addresses.exists()


# --- staff management guards -------------------------------------------------------------------


def test_cannot_deactivate_or_delete_yourself_or_the_last_admin():
    admin = AdminFactory()
    with pytest.raises(ValidationError):
        services.set_user_active(admin, admin, False)
    with pytest.raises(ValidationError):
        services.delete_staff(admin, admin)
    second = AdminFactory()
    # with two admins, one may remove the other...
    services.set_user_active(second, admin, False)
    # ...but not when that leaves nobody: `second` is now inactive, `admin` is the last one.
    third = CCEFactory()
    with pytest.raises(ValidationError) as exc:
        services.update_staff(admin, third, role=User.Role.CCE)
    assert exc.value.code == "last_admin"


def test_cannot_change_own_role():
    admin, _other = AdminFactory(), AdminFactory()
    with pytest.raises(ValidationError) as exc:
        services.update_staff(admin, admin, role=User.Role.CCE)
    assert exc.value.code == "self_role_change"


def test_deactivating_revokes_refresh_tokens():
    admin, cce = AdminFactory(), CCEFactory()
    refresh = str(RefreshToken.for_user(cce))
    services.set_user_active(cce, admin, False)
    with pytest.raises(Exception):
        RefreshToken(refresh)
    assert OutstandingToken.objects.filter(user=cce).count() == 1


def test_admin_password_reset_clears_flag_and_revokes_sessions():
    admin, cce = AdminFactory(), CCEFactory(must_change_password=True)
    refresh = str(RefreshToken.for_user(cce))
    services.update_staff(cce, admin, password="N3w!Str0ngPassw0rd", full_name="Renamed")
    cce.refresh_from_db()
    assert cce.check_password("N3w!Str0ngPassw0rd") and cce.full_name == "Renamed" and not cce.must_change_password
    with pytest.raises(Exception):
        RefreshToken(refresh)
