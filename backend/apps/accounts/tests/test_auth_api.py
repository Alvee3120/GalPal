import re

import pytest
from django.core import mail
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.core.messaging import LocMemSMSBackend

from .factories import UserFactory

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/auth/register/"
LOGIN = "/api/v1/auth/login/"
REFRESH = "/api/v1/auth/token/refresh/"
LOGOUT = "/api/v1/auth/logout/"
CHANGE = "/api/v1/auth/password/change/"
FORGOT = "/api/v1/auth/password/forgot/"
RESET = "/api/v1/auth/password/reset/"
PROFILE = "/api/v1/account/profile/"

NEW_PASSWORD = "N3w!Str0ngPassw0rd"


def post(client, url, data):
    return client.post(url, data, format="json")


# --- registration -------------------------------------------------------------------------


def test_register_creates_customer_and_returns_tokens(api_client):
    response = post(api_client, REGISTER, {"full_name": "Rina Akter", "phone": "+8801712345678", "password": NEW_PASSWORD})
    assert response.status_code == 201
    body = response.json()
    assert body["access"] and body["refresh"] and body["must_change_password"] is False
    assert body["user"]["phone"] == "01712345678" and body["user"]["role"] == "customer"
    assert "password" not in body["user"]
    user = User.objects.get(phone="01712345678")
    assert user.role == User.Role.CUSTOMER and user.email is None and not user.created_via_checkout


def test_register_cannot_choose_a_role(api_client):
    post(api_client, REGISTER, {"full_name": "Sneaky", "phone": "01712345678", "password": NEW_PASSWORD, "role": "admin"})
    assert User.objects.get().role == User.Role.CUSTOMER


def test_registered_access_token_works(api_client):
    body = post(api_client, REGISTER, {"full_name": "R", "phone": "01712345678", "password": NEW_PASSWORD}).json()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    assert api_client.get(PROFILE).json()["phone"] == "01712345678"


@pytest.mark.parametrize(
    "payload,field",
    [
        ({"full_name": "R", "phone": "12345", "password": NEW_PASSWORD}, "phone"),
        ({"full_name": "R", "phone": "01712345678", "password": "short"}, "password"),
        ({"full_name": "R", "phone": "01712345678", "password": "12345678"}, "password"),
        ({"full_name": "R", "phone": "01712345678", "password": "password123"}, "password"),
        ({"full_name": "R", "phone": "01712345678", "password": NEW_PASSWORD, "email": "not-an-email"}, "email"),
        ({"phone": "01712345678", "password": NEW_PASSWORD}, "full_name"),
        ({"full_name": "R", "password": NEW_PASSWORD}, "phone"),
    ],
)
def test_register_validation_errors(api_client, payload, field):
    response = post(api_client, REGISTER, payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert field in response.json()["error"]["details"]


def test_register_rejects_duplicate_phone_in_any_format_and_duplicate_email(api_client):
    UserFactory(phone="01712345678", email="taken@example.com")
    r = post(api_client, REGISTER, {"full_name": "R", "phone": "+8801712345678", "password": NEW_PASSWORD})
    assert r.status_code == 400 and "phone" in r.json()["error"]["details"]
    r = post(api_client, REGISTER, {"full_name": "R", "phone": "01812345678", "email": "TAKEN@example.com", "password": NEW_PASSWORD})
    assert r.status_code == 400 and "email" in r.json()["error"]["details"]


def test_register_password_similar_to_phone_is_rejected(api_client):
    r = post(api_client, REGISTER, {"full_name": "Rinaakter", "phone": "01712345678", "password": "rinaakter1"})
    assert r.status_code == 400


# --- login -------------------------------------------------------------------------------------


@pytest.mark.parametrize("identifier", ["01712345678", "+8801712345678", "8801712345678", "rina@example.com", "RINA@example.com"])
def test_login_by_phone_or_email(api_client, password, identifier):
    UserFactory(phone="01712345678", email="rina@example.com", full_name="Rina")
    response = post(api_client, LOGIN, {"identifier": identifier, "password": password})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access", "refresh", "must_change_password", "user"}
    assert body["user"]["full_name"] == "Rina" and body["must_change_password"] is False


def test_login_sets_last_login(api_client, password):
    user = UserFactory()
    assert user.last_login is None
    post(api_client, LOGIN, {"identifier": user.phone, "password": password})
    user.refresh_from_db()
    assert user.last_login is not None


def test_login_response_carries_must_change_password_flag(api_client, password):
    user = UserFactory(must_change_password=True, created_via_checkout=True)
    body = post(api_client, LOGIN, {"identifier": user.phone, "password": password}).json()
    assert body["must_change_password"] is True
    assert body["user"]["must_change_password"] is True and body["user"]["created_via_checkout"] is True


def test_login_wrong_password_and_unknown_user_look_the_same(api_client, password):
    UserFactory(phone="01712345678")
    wrong = post(api_client, LOGIN, {"identifier": "01712345678", "password": "nope"})
    unknown = post(api_client, LOGIN, {"identifier": "01899999999", "password": "nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error"]["code"] == "invalid_credentials"


def test_login_deactivated_account_is_403(api_client, password):
    user = UserFactory(is_active=False)
    response = post(api_client, LOGIN, {"identifier": user.phone, "password": password})
    assert response.status_code == 403 and response.json()["error"]["code"] == "account_disabled"


def test_login_ignores_a_stale_authorization_header(api_client, password):
    user = UserFactory()
    api_client.credentials(HTTP_AUTHORIZATION="Bearer expired.or.garbage")
    assert post(api_client, LOGIN, {"identifier": user.phone, "password": password}).status_code == 200


def test_login_requires_both_fields(api_client):
    r = post(api_client, LOGIN, {})
    assert r.status_code == 400 and set(r.json()["error"]["details"]) == {"identifier", "password"}


# --- refresh & logout --------------------------------------------------------------------------


def login_tokens(client, user, password):
    return post(client, LOGIN, {"identifier": user.phone, "password": password}).json()


def test_refresh_rotates_and_blacklists_the_old_token(api_client, password):
    tokens = login_tokens(api_client, UserFactory(), password)
    first = post(api_client, REFRESH, {"refresh": tokens["refresh"]})
    assert first.status_code == 200 and first.json()["access"] and first.json()["refresh"] != tokens["refresh"]
    reuse = post(api_client, REFRESH, {"refresh": tokens["refresh"]})
    assert reuse.status_code == 401 and reuse.json()["error"]["code"] == "token_not_valid"


def test_refresh_with_garbage_is_401_envelope(api_client):
    r = post(api_client, REFRESH, {"refresh": "garbage"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "token_not_valid"


def test_logout_blacklists_refresh_token(api_client, password):
    tokens = login_tokens(api_client, UserFactory(), password)
    assert post(api_client, LOGOUT, {"refresh": tokens["refresh"]}).status_code == 204
    assert post(api_client, REFRESH, {"refresh": tokens["refresh"]}).status_code == 401
    again = post(api_client, LOGOUT, {"refresh": tokens["refresh"]})
    assert again.status_code == 400 and "refresh" in again.json()["error"]["details"]


def test_logout_requires_refresh_field_and_valid_token(api_client):
    assert post(api_client, LOGOUT, {}).status_code == 400
    assert post(api_client, LOGOUT, {"refresh": "garbage"}).status_code == 400


def test_deactivated_user_cannot_refresh_or_use_access_token(api_client, auth_client, password):
    user = UserFactory()
    tokens = login_tokens(api_client, user, password)
    user.is_active = False
    user.save()
    assert post(api_client, REFRESH, {"refresh": tokens["refresh"]}).status_code == 401
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert api_client.get(PROFILE).status_code == 401


def test_protected_endpoint_without_token_is_401(api_client):
    r = api_client.get(PROFILE)
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_authenticated"


# --- change password ---------------------------------------------------------------------------


def test_change_password_success_clears_flag_and_returns_new_tokens(auth_client, api_client, password):
    user = UserFactory(must_change_password=True)
    old_refresh = str(RefreshToken.for_user(user))
    response = post(auth_client(user), CHANGE, {"old_password": password, "new_password": NEW_PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["access"] and body["refresh"] and body["detail"]
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD) and user.must_change_password is False
    assert post(api_client, REFRESH, {"refresh": old_refresh}).status_code == 401  # other devices logged out
    assert post(api_client, REFRESH, {"refresh": body["refresh"]}).status_code == 200
    assert post(api_client, LOGIN, {"identifier": user.phone, "password": NEW_PASSWORD}).json()["must_change_password"] is False


def test_change_password_wrong_old_password(auth_client, customer):
    r = post(auth_client(customer), CHANGE, {"old_password": "wrong", "new_password": NEW_PASSWORD})
    assert r.status_code == 400 and "old_password" in r.json()["error"]["details"]


def test_change_password_rejects_weak_or_same_password(auth_client, customer, password):
    client = auth_client(customer)
    assert "new_password" in post(client, CHANGE, {"old_password": password, "new_password": "12345678"}).json()["error"]["details"]
    assert "new_password" in post(client, CHANGE, {"old_password": password, "new_password": password}).json()["error"]["details"]


def test_change_password_requires_login(api_client):
    assert post(api_client, CHANGE, {"old_password": "a", "new_password": "b"}).status_code == 401


# --- forgot / reset -----------------------------------------------------------------------------


def sms_code():
    return re.search(r"\b(\d{6})\b", LocMemSMSBackend.outbox[-1]["message"]).group(1)


def test_forgot_response_is_identical_for_existing_and_unknown_accounts(api_client):
    UserFactory(phone="01712345678")
    known = post(api_client, FORGOT, {"identifier": "01712345678"})
    unknown = post(api_client, FORGOT, {"identifier": "01899999999"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert len(LocMemSMSBackend.outbox) == 1


def test_full_forgot_and_reset_flow_by_phone(api_client):
    user = UserFactory(phone="01712345678", must_change_password=True)
    post(api_client, FORGOT, {"identifier": "01712345678"})
    response = post(api_client, RESET, {"identifier": "01712345678", "otp": sms_code(), "new_password": NEW_PASSWORD})
    assert response.status_code == 200
    login = post(api_client, LOGIN, {"identifier": "01712345678", "password": NEW_PASSWORD})
    assert login.status_code == 200 and login.json()["must_change_password"] is False


def test_full_forgot_and_reset_flow_by_email(api_client):
    UserFactory(email="rina@example.com")
    post(api_client, FORGOT, {"identifier": "rina@example.com"})
    code = re.search(r"\b(\d{6})\b", mail.outbox[0].body).group(1)
    assert post(api_client, RESET, {"identifier": "rina@example.com", "otp": code, "new_password": NEW_PASSWORD}).status_code == 200
    assert post(api_client, LOGIN, {"identifier": "rina@example.com", "password": NEW_PASSWORD}).status_code == 200


def test_reset_with_wrong_code_is_400_invalid_otp(api_client):
    UserFactory(phone="01712345678")
    post(api_client, FORGOT, {"identifier": "01712345678"})
    wrong = "000000" if sms_code() != "000000" else "111111"
    r = post(api_client, RESET, {"identifier": "01712345678", "otp": wrong, "new_password": NEW_PASSWORD})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_otp"
    unknown = post(api_client, RESET, {"identifier": "01899999999", "otp": "123456", "new_password": NEW_PASSWORD})
    assert unknown.json() == r.json()  # same answer for unknown accounts


def test_reset_validates_otp_format_and_password_strength_without_burning_the_code(api_client):
    user = UserFactory(phone="01712345678")
    post(api_client, FORGOT, {"identifier": "01712345678"})
    code = sms_code()
    assert "otp" in post(api_client, RESET, {"identifier": user.phone, "otp": "12", "new_password": NEW_PASSWORD}).json()["error"]["details"]
    assert "new_password" in post(api_client, RESET, {"identifier": user.phone, "otp": code, "new_password": "12345678"}).json()["error"]["details"]
    assert post(api_client, RESET, {"identifier": user.phone, "otp": code, "new_password": NEW_PASSWORD}).status_code == 200


def test_reset_revokes_existing_sessions(api_client, password):
    user = UserFactory(phone="01712345678")
    tokens = login_tokens(api_client, user, password)
    post(api_client, FORGOT, {"identifier": user.phone})
    post(api_client, RESET, {"identifier": user.phone, "otp": sms_code(), "new_password": NEW_PASSWORD})
    assert post(api_client, REFRESH, {"refresh": tokens["refresh"]}).status_code == 401
