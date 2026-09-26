import pytest

from apps.accounts.models import User

pytestmark = pytest.mark.django_db
URL = "/api/v1/admin/users/"
STRONG = "Rose-Garden-2026!"


@pytest.fixture
def admin_client(auth_client, admin_user):
    return auth_client(admin_user)


def body(**overrides):
    return {"phone": "01911112222", "full_name": "Nabila Islam", "role": "cce", "password": STRONG, "password_confirm": STRONG, **overrides}


def test_only_admins_get_in(auth_client, cce_user, customer, api_client):
    assert api_client.get(URL).status_code == 401
    assert auth_client(cce_user).get(URL).status_code == 403
    assert auth_client(customer).get(URL).status_code == 403


def test_list_search_and_role_filter_never_show_passwords(admin_client, cce_user, customer):
    rows = admin_client.get(URL).json()["results"]
    assert rows and all("password" not in r for r in rows)
    assert {r["role"] for r in admin_client.get(f"{URL}?role=customer").json()["results"]} == {"customer"}
    found = admin_client.get(URL, {"search": customer.full_name.split()[0], "role": "customer"}).json()["results"]
    assert [r["id"] for r in found] == [customer.id]


@pytest.mark.parametrize(
    "password, field",
    [("12345678", "password"), ("short1!", "password"), ("password123", "password"), ("nabilaislam1", "password")],
)
def test_passwords_follow_the_django_validators(admin_client, password, field):
    r = admin_client.post(URL, body(password=password, password_confirm=password), format="json")
    assert r.status_code == 400 and field in r.json()["error"]["details"]


def test_confirmation_must_match(admin_client):
    r = admin_client.post(URL, body(password_confirm="Something-Else-99"), format="json")
    assert r.status_code == 400 and r.json()["error"]["details"]["password_confirm"] == ["Passwords do not match."]


def test_create_then_edit_keeping_or_changing_the_password(admin_client):
    created = admin_client.post(URL, body(), format="json")
    assert created.status_code == 201 and "password" not in created.json()
    user = User.objects.get(pk=created.json()["id"])
    assert user.role == "cce" and not user.created_via_checkout and user.check_password(STRONG)

    url = f"{URL}{user.pk}/"
    r = admin_client.patch(url, {"full_name": "Nabila I.", "role": "customer", "is_active": False, "password": "", "password_confirm": ""}, format="json")
    assert r.status_code == 200 and (r.json()["role"], r.json()["is_active"]) == ("customer", False)
    user.refresh_from_db()
    assert user.check_password(STRONG)  # empty password fields keep it

    new = "Lotus-Bloom-8842"
    assert admin_client.patch(url, {"password": new, "password_confirm": new}, format="json").status_code == 200
    user.refresh_from_db()
    assert user.check_password(new)


def test_admins_cannot_lock_themselves_out(admin_client, admin_user):
    url = f"{URL}{admin_user.pk}/"
    assert admin_client.patch(url, {"role": "cce"}, format="json").status_code == 400
    assert admin_client.patch(url, {"is_active": False}, format="json").status_code == 400
    assert admin_client.delete(url).status_code == 400
    assert User.objects.filter(pk=admin_user.pk, role="admin", is_active=True).exists()


def test_deleting_a_customer_keeps_their_orders(admin_client, customer):
    from apps.orders.tests.helpers import new_order

    order = new_order(customer=customer)
    assert admin_client.delete(f"{URL}{customer.pk}/").status_code == 204
    order.refresh_from_db()
    assert order.customer_id is None and not User.objects.filter(pk=customer.pk).exists()


def test_admin_can_upload_and_remove_an_avatar(admin_client):
    from apps.catalog.tests.factories import make_image

    created = admin_client.post(URL, {**body(), "avatar": make_image()}, format="multipart")
    assert created.status_code == 201 and created.json()["avatar"]
    url = f"{URL}{created.json()['id']}/"
    assert admin_client.patch(url, {"avatar": ""}, format="multipart").json()["avatar"] is None


def test_a_reset_password_is_temporary(admin_client, customer):
    temp = "Tmp-Reset-7Qx9Lm"
    r = admin_client.patch(f"{URL}{customer.pk}/", {"password": temp, "password_confirm": temp, "must_change_password": True}, format="json")
    assert r.status_code == 200 and r.json()["must_change_password"] is True and "password" not in r.json()
    customer.refresh_from_db()
    assert customer.check_password(temp) and customer.must_change_password
