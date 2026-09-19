import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import Address, User

from .factories import AddressFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_create_user_defaults():
    user = User.objects.create_user(phone="01712345678", full_name="Rina", password="Str0ng!Passw0rd")
    assert user.role == User.Role.CUSTOMER and user.is_customer
    assert user.is_active and not user.is_staff and not user.is_superuser
    assert not user.created_via_checkout and not user.must_change_password
    assert user.email is None
    assert user.check_password("Str0ng!Passw0rd") and user.password != "Str0ng!Passw0rd"
    assert str(user) == "Rina (01712345678)"
    assert user.created_at and user.updated_at


def test_phone_is_normalised_on_save():
    user = User.objects.create_user(phone="+880 1712-345678", full_name="A")
    assert user.phone == "01712345678"


def test_invalid_phone_is_rejected():
    with pytest.raises(ValidationError):
        User.objects.create_user(phone="12345", full_name="A")


def test_phone_is_unique_across_formats():
    User.objects.create_user(phone="01712345678", full_name="A")
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(phone="+8801712345678", full_name="B")


def test_email_is_optional_lowercased_and_unique():
    a = UserFactory(email="")
    b = UserFactory(email=None)
    assert a.email is None and b.email is None  # many users may have no email
    c = UserFactory(email="Mixed@Example.COM")
    assert c.email == "mixed@example.com"
    with pytest.raises(IntegrityError), transaction.atomic():
        UserFactory(email="MIXED@example.com")


def test_role_drives_django_admin_access():
    admin = UserFactory(role=User.Role.ADMIN)
    assert admin.is_staff and admin.is_superuser and admin.is_admin
    cce = UserFactory(role=User.Role.CCE)
    assert not cce.is_staff and not cce.is_superuser and cce.is_cce
    admin.role = User.Role.CUSTOMER
    admin.save()
    admin.refresh_from_db()
    assert not admin.is_staff and not admin.is_superuser
    admin.is_staff = True  # can't be set by hand
    admin.save(update_fields=["full_name"])
    admin.refresh_from_db()
    assert not admin.is_staff


def test_create_superuser_is_admin_role():
    user = User.objects.create_superuser(phone="01712345678", full_name="Root", password="Str0ng!Passw0rd")
    assert user.role == User.Role.ADMIN and user.is_staff and user.is_superuser


def test_get_by_identifier_finds_by_phone_or_email():
    user = UserFactory(phone="01712345678", email="rina@example.com")
    for identifier in ["01712345678", "+8801712345678", "8801712345678", "rina@example.com", " RINA@Example.com "]:
        assert User.objects.get_by_identifier(identifier) == user
    for identifier in ["", None, "01812345678", "nobody@example.com", "garbage"]:
        assert User.objects.get_by_identifier(identifier) is None


def test_login_identifier_is_phone():
    assert User.USERNAME_FIELD == "phone"


def test_address_normalises_phone_and_orders_default_first():
    user = UserFactory()
    first = AddressFactory(user=user, phone="+8801812345678")
    second = AddressFactory(user=user, is_default=True)
    assert first.phone == "01812345678"
    assert list(user.addresses.all()) == [second, first]


def test_database_allows_only_one_default_address_per_user():
    user = UserFactory()
    AddressFactory(user=user, is_default=True)
    AddressFactory(user=UserFactory(), is_default=True)  # another user: fine
    with pytest.raises(IntegrityError), transaction.atomic():
        AddressFactory(user=user, is_default=True)


def test_deleting_user_deletes_addresses():
    address = AddressFactory()
    address.user.delete()
    assert not Address.objects.filter(pk=address.pk).exists()
