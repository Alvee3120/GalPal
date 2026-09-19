import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.models import Address

from .factories import AddressFactory, UserFactory

pytestmark = pytest.mark.django_db

PROFILE = "/api/v1/account/profile/"
ADDRESSES = "/api/v1/account/addresses/"

ADDRESS_PAYLOAD = {
    "label": "Home", "full_name": "Rina Akter", "phone": "+8801812345678", "division": "Dhaka",
    "district": "Dhaka", "area": "Mirpur", "address_line": "House 5, Road 3", "postal_code": "1216",
}


def png(name="a.png", fmt="PNG"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "pink").save(buffer, format=fmt)
    return SimpleUploadedFile(name, buffer.getvalue())


# --- profile ------------------------------------------------------------------------------


def test_get_own_profile(auth_client):
    user = UserFactory(full_name="Rina", phone="01712345678", email="rina@example.com")
    body = auth_client(user).get(PROFILE).json()
    assert body["full_name"] == "Rina" and body["phone"] == "01712345678" and body["role"] == "customer"
    assert body["avatar"] is None and "password" not in body


def test_patch_name_and_email(auth_client):
    user = UserFactory()
    r = auth_client(user).patch(PROFILE, {"full_name": "New Name", "email": "NEW@Example.com"}, format="json")
    assert r.status_code == 200
    user.refresh_from_db()
    assert user.full_name == "New Name" and user.email == "new@example.com"


def test_profile_readonly_fields_cannot_be_changed(auth_client):
    user = UserFactory(phone="01712345678")
    auth_client(user).patch(
        PROFILE,
        {"phone": "01812345678", "role": "admin", "must_change_password": True, "created_via_checkout": True},
        format="json",
    )
    user.refresh_from_db()
    assert user.phone == "01712345678" and user.role == "customer"
    assert not user.must_change_password and not user.created_via_checkout


def test_profile_email_must_be_unique_but_may_keep_own_or_be_cleared(auth_client):
    UserFactory(email="taken@example.com")
    user = UserFactory(email="mine@example.com")
    client = auth_client(user)
    assert client.patch(PROFILE, {"email": "taken@example.com"}, format="json").status_code == 400
    assert client.patch(PROFILE, {"email": "mine@example.com"}, format="json").status_code == 200
    assert client.patch(PROFILE, {"email": ""}, format="json").status_code == 200
    user.refresh_from_db()
    assert user.email is None


def test_avatar_upload_returns_absolute_url_and_validates_type(auth_client):
    user = UserFactory()
    client = auth_client(user)
    ok = client.patch(PROFILE, {"avatar": png("me.png")}, format="multipart")
    assert ok.status_code == 200 and ok.json()["avatar"].startswith("http://testserver/media/avatars/")
    bad = client.patch(PROFILE, {"avatar": png("me.gif", "GIF")}, format="multipart")
    assert bad.status_code == 400 and "avatar" in bad.json()["error"]["details"]
    fake = client.patch(PROFILE, {"avatar": SimpleUploadedFile("x.png", b"not an image")}, format="multipart")
    assert fake.status_code == 400


def test_profile_put_and_delete_not_allowed(auth_client, customer):
    client = auth_client(customer)
    assert client.put(PROFILE, {}, format="json").status_code == 405
    assert client.delete(PROFILE).status_code == 405


# --- address book -------------------------------------------------------------------------


def test_addresses_require_login(api_client):
    assert api_client.get(ADDRESSES).status_code == 401
    assert api_client.post(ADDRESSES, ADDRESS_PAYLOAD, format="json").status_code == 401


def test_create_address_first_is_default_and_phone_is_normalised(auth_client, customer):
    r = auth_client(customer).post(ADDRESSES, ADDRESS_PAYLOAD, format="json")
    assert r.status_code == 201
    body = r.json()
    assert body["is_default"] is True and body["phone"] == "01812345678"
    assert set(body) >= {"id", "label", "full_name", "phone", "division", "district", "area", "address_line", "postal_code", "is_default"}
    assert "user" not in body


def test_second_address_is_not_default_unless_asked(auth_client, customer):
    client = auth_client(customer)
    client.post(ADDRESSES, ADDRESS_PAYLOAD, format="json")
    second = client.post(ADDRESSES, {**ADDRESS_PAYLOAD, "label": "Office"}, format="json").json()
    assert second["is_default"] is False
    third = client.post(ADDRESSES, {**ADDRESS_PAYLOAD, "label": "Mom", "is_default": True}, format="json").json()
    assert third["is_default"] is True
    assert customer.addresses.filter(is_default=True).count() == 1


def test_list_is_paginated_and_default_first(auth_client, customer):
    AddressFactory(user=customer, label="old")
    default = AddressFactory(user=customer, label="main", is_default=True)
    body = auth_client(customer).get(ADDRESSES).json()
    assert set(body) == {"count", "next", "previous", "results"} and body["count"] == 2
    assert body["results"][0]["id"] == default.id


def test_address_validation(auth_client, customer):
    r = auth_client(customer).post(ADDRESSES, {"full_name": "R", "phone": "123"}, format="json")
    assert r.status_code == 400
    assert set(r.json()["error"]["details"]) >= {"phone", "district", "address_line"}


def test_patch_and_retrieve_address(auth_client, customer):
    address = AddressFactory(user=customer, is_default=True)
    client = auth_client(customer)
    r = client.patch(f"{ADDRESSES}{address.id}/", {"area": "Gulshan", "postal_code": "1212"}, format="json")
    assert r.status_code == 200 and r.json()["area"] == "Gulshan"
    assert client.get(f"{ADDRESSES}{address.id}/").json()["postal_code"] == "1212"


def test_cannot_unset_default_directly(auth_client, customer):
    address = AddressFactory(user=customer, is_default=True)
    r = auth_client(customer).patch(f"{ADDRESSES}{address.id}/", {"is_default": False}, format="json")
    assert r.status_code == 400 and "is_default" in r.json()["error"]["details"]


def test_set_default_action(auth_client, customer):
    a1 = AddressFactory(user=customer, is_default=True)
    a2 = AddressFactory(user=customer)
    r = auth_client(customer).post(f"{ADDRESSES}{a2.id}/set-default/")
    assert r.status_code == 200 and r.json()["is_default"] is True
    a1.refresh_from_db()
    assert not a1.is_default


def test_delete_default_promotes_another(auth_client, customer):
    a1 = AddressFactory(user=customer, is_default=True)
    a2 = AddressFactory(user=customer)
    assert auth_client(customer).delete(f"{ADDRESSES}{a1.id}/").status_code == 204
    a2.refresh_from_db()
    assert a2.is_default


def test_users_cannot_see_or_touch_each_others_addresses(auth_client):
    owner, intruder = UserFactory(), UserFactory()
    address = AddressFactory(user=owner)
    client = auth_client(intruder)
    assert client.get(ADDRESSES).json()["count"] == 0
    assert client.get(f"{ADDRESSES}{address.id}/").status_code == 404
    assert client.patch(f"{ADDRESSES}{address.id}/", {"area": "x"}, format="json").status_code == 404
    assert client.delete(f"{ADDRESSES}{address.id}/").status_code == 404
    assert client.post(f"{ADDRESSES}{address.id}/set-default/").status_code == 404
    assert Address.objects.filter(pk=address.pk).exists()


def test_user_field_in_payload_cannot_assign_address_to_someone_else(auth_client):
    me, victim = UserFactory(), UserFactory()
    auth_client(me).post(ADDRESSES, {**ADDRESS_PAYLOAD, "user": victim.id}, format="json")
    assert me.addresses.count() == 1 and victim.addresses.count() == 0
