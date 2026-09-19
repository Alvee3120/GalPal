import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User

from .factories import AddressFactory, AdminFactory, CCEFactory, UserFactory

pytestmark = pytest.mark.django_db

STAFF = "/api/v1/admin/staff/"
CUSTOMERS = "/api/v1/admin/customers/"
STRONG = "N3w!Str0ngPassw0rd"


# --- staff ---------------------------------------------------------------------------------


def test_admin_creates_cce_account_by_default(auth_client, admin_user):
    r = auth_client(admin_user).post(
        STAFF, {"full_name": "Care Exec", "phone": "01911111111", "password": STRONG}, format="json"
    )
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "cce" and body["is_active"] is True and "password" not in body
    cce = User.objects.get(phone="01911111111")
    assert cce.role == User.Role.CCE and cce.check_password(STRONG) and not cce.is_staff


def test_admin_can_create_another_admin(auth_client, admin_user):
    r = auth_client(admin_user).post(
        STAFF, {"full_name": "Boss", "phone": "01911111112", "password": STRONG, "role": "admin"}, format="json"
    )
    assert r.status_code == 201 and User.objects.get(phone="01911111112").is_superuser


def test_staff_cannot_be_created_as_customer_role(auth_client, admin_user):
    r = auth_client(admin_user).post(
        STAFF, {"full_name": "X", "phone": "01911111113", "password": STRONG, "role": "customer"}, format="json"
    )
    assert r.status_code == 400 and "role" in r.json()["error"]["details"]


def test_staff_create_validation(auth_client, admin_user):
    existing = UserFactory(phone="01911111111")
    client = auth_client(admin_user)
    r = client.post(STAFF, {"full_name": "X", "phone": "+8801911111111", "password": STRONG}, format="json")
    assert r.status_code == 400 and set(r.json()["error"]["details"]) == {"phone"}
    r = client.post(STAFF, {"full_name": "X", "phone": "01911111119", "password": "short"}, format="json")
    assert r.status_code == 400 and set(r.json()["error"]["details"]) == {"password"}
    assert existing.role == User.Role.CUSTOMER and User.objects.count() == 2


def test_staff_list_only_shows_admin_and_cce_and_supports_filters(auth_client, admin_user):
    cce = CCEFactory(full_name="Zed Care", phone="01922222222", is_active=False)
    UserFactory()  # customers are not staff
    client = auth_client(admin_user)
    body = client.get(STAFF).json()
    assert body["count"] == 2 and {u["role"] for u in body["results"]} == {"admin", "cce"}
    assert [u["id"] for u in client.get(f"{STAFF}?role=cce").json()["results"]] == [cce.id]
    assert [u["id"] for u in client.get(f"{STAFF}?is_active=false").json()["results"]] == [cce.id]
    assert [u["id"] for u in client.get(f"{STAFF}?search=%2B880 1922-222222").json()["results"]] == [cce.id]
    assert [u["id"] for u in client.get(f"{STAFF}?search=zed").json()["results"]] == [cce.id]


def test_staff_detail_hides_customers(auth_client, admin_user, customer):
    assert auth_client(admin_user).get(f"{STAFF}{customer.id}/").status_code == 404


def test_staff_update_and_password_reset_by_admin(auth_client, admin_user):
    cce = CCEFactory(must_change_password=True)
    refresh = str(RefreshToken.for_user(cce))
    r = auth_client(admin_user).patch(
        f"{STAFF}{cce.id}/", {"full_name": "Renamed", "email": "", "password": STRONG}, format="json"
    )
    assert r.status_code == 200 and r.json()["full_name"] == "Renamed"
    cce.refresh_from_db()
    assert cce.check_password(STRONG) and cce.email is None and not cce.must_change_password
    with pytest.raises(Exception):
        RefreshToken(refresh)


def test_staff_update_rejects_taken_phone_but_allows_own(auth_client, admin_user):
    UserFactory(phone="01933333333")
    cce = CCEFactory(phone="01944444444")
    client = auth_client(admin_user)
    assert client.patch(f"{STAFF}{cce.id}/", {"phone": "01933333333"}, format="json").status_code == 400
    assert client.patch(f"{STAFF}{cce.id}/", {"phone": "+8801944444444"}, format="json").status_code == 200


def test_admin_cannot_change_own_role_or_deactivate_or_delete_self(auth_client, admin_user):
    AdminFactory()
    client = auth_client(admin_user)
    assert client.patch(f"{STAFF}{admin_user.id}/", {"role": "cce"}, format="json").status_code == 400
    assert client.post(f"{STAFF}{admin_user.id}/deactivate/").status_code == 400
    assert client.delete(f"{STAFF}{admin_user.id}/").status_code == 400
    admin_user.refresh_from_db()
    assert admin_user.is_active and admin_user.is_admin


def test_admin_can_demote_another_admin_while_one_remains(auth_client, admin_user):
    # (The "never zero active admins" guard itself is covered in test_services.)
    other = AdminFactory()
    r = auth_client(admin_user).patch(f"{STAFF}{other.id}/", {"role": "cce"}, format="json")
    assert r.status_code == 200 and r.json()["role"] == "cce"
    other.refresh_from_db()
    assert not other.is_superuser


def test_activate_and_deactivate_staff_block_login(auth_client, api_client, admin_user, password):
    cce = CCEFactory()
    client = auth_client(admin_user)
    r = client.post(f"{STAFF}{cce.id}/deactivate/")
    assert r.status_code == 200 and r.json()["is_active"] is False
    login = api_client.post("/api/v1/auth/login/", {"identifier": cce.phone, "password": password}, format="json")
    assert login.status_code == 403
    assert client.post(f"{STAFF}{cce.id}/activate/").json()["is_active"] is True
    assert api_client.post("/api/v1/auth/login/", {"identifier": cce.phone, "password": password}, format="json").status_code == 200


def test_deleted_staff_is_gone(auth_client, admin_user):
    cce = CCEFactory()
    assert auth_client(admin_user).delete(f"{STAFF}{cce.id}/").status_code == 204
    assert not User.objects.filter(pk=cce.pk).exists()


def test_staff_put_not_supported(auth_client, admin_user):
    cce = CCEFactory()
    assert auth_client(admin_user).put(f"{STAFF}{cce.id}/", {}, format="json").status_code == 405


# --- customers -----------------------------------------------------------------------------


def test_customer_list_excludes_staff_and_is_paginated(auth_client, admin_user):
    UserFactory.create_batch(3)
    CCEFactory()
    body = auth_client(admin_user).get(CUSTOMERS).json()
    assert body["count"] == 3 and set(body) == {"count", "next", "previous", "results"}
    assert all("addresses" not in row and "password" not in row for row in body["results"])


def test_customer_search_by_name_phone_any_format_and_email(auth_client, admin_user):
    rina = UserFactory(full_name="Rina Akter", phone="01712345678", email="rina@shop.com")
    UserFactory(full_name="Someone Else")
    client = auth_client(admin_user)
    for query in ["rina", "AKTER", "01712345678", "%2B8801712345678", "8801712-345678", "rina@shop", "1712345"]:
        assert [c["id"] for c in client.get(f"{CUSTOMERS}?search={query}").json()["results"]] == [rina.id], query
    assert client.get(f"{CUSTOMERS}?search=nomatchxyz").json()["count"] == 0


def test_customer_filters(auth_client, admin_user):
    active = UserFactory()
    inactive = UserFactory(is_active=False)
    checkout = UserFactory(created_via_checkout=True)
    old = UserFactory()
    User.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=40))
    client = auth_client(admin_user)
    ids = lambda qs: {c["id"] for c in client.get(f"{CUSTOMERS}?{qs}").json()["results"]}  # noqa: E731
    assert ids("is_active=false") == {inactive.id}
    assert ids("created_via_checkout=true") == {checkout.id}
    assert old.id not in ids(f"created_after={(timezone.now() - timedelta(days=30)).date()}")
    assert ids(f"created_before={(timezone.now() - timedelta(days=30)).date()}") == {old.id}
    assert active.id in ids("is_active=true")


def test_customer_ordering(auth_client, admin_user):
    b, a = UserFactory(full_name="Bbb"), UserFactory(full_name="Aaa")
    names = [c["full_name"] for c in auth_client(admin_user).get(f"{CUSTOMERS}?ordering=full_name").json()["results"]]
    assert names == ["Aaa", "Bbb"]
    assert names[0] == a.full_name and b


def test_customer_detail_includes_address_book(auth_client, admin_user, customer):
    AddressFactory(user=customer, label="Home", is_default=True)
    AddressFactory(user=customer, label="Office")
    body = auth_client(admin_user).get(f"{CUSTOMERS}{customer.id}/").json()
    assert body["phone"] == customer.phone and len(body["addresses"]) == 2
    assert body["addresses"][0]["is_default"] is True and "password" not in body


def test_customer_detail_404_for_staff_ids(auth_client, admin_user, cce_user):
    assert auth_client(admin_user).get(f"{CUSTOMERS}{cce_user.id}/").status_code == 404


def test_customer_is_read_only_via_api(auth_client, admin_user, customer):
    client = auth_client(admin_user)
    assert client.post(CUSTOMERS, {}, format="json").status_code == 405
    assert client.patch(f"{CUSTOMERS}{customer.id}/", {"full_name": "x"}, format="json").status_code == 405
    assert client.delete(f"{CUSTOMERS}{customer.id}/").status_code == 405


def test_deactivate_and_activate_customer(auth_client, api_client, admin_user, customer, password):
    client = auth_client(admin_user)
    refresh = str(RefreshToken.for_user(customer))
    assert client.post(f"{CUSTOMERS}{customer.id}/deactivate/").json()["is_active"] is False
    assert api_client.post("/api/v1/auth/login/", {"identifier": customer.phone, "password": password}, format="json").status_code == 403
    assert api_client.post("/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json").status_code == 401
    assert client.post(f"{CUSTOMERS}{customer.id}/activate/").json()["is_active"] is True
    assert api_client.post("/api/v1/auth/login/", {"identifier": customer.phone, "password": password}, format="json").status_code == 200
