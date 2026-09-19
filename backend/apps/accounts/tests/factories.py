import factory

from apps.accounts.models import Address, User

DEFAULT_PASSWORD = "Str0ng!Passw0rd"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    phone = factory.Sequence(lambda n: f"017{n:08d}")
    full_name = factory.Sequence(lambda n: f"Test User {n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    role = User.Role.CUSTOMER
    password = factory.PostGenerationMethodCall("set_password", DEFAULT_PASSWORD)

    @factory.post_generation
    def _save_password(obj, create, extracted, **kwargs):
        if create:
            obj.save()


class AdminFactory(UserFactory):
    role = User.Role.ADMIN


class CCEFactory(UserFactory):
    role = User.Role.CCE


class AddressFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Address

    user = factory.SubFactory(UserFactory)
    label = "Home"
    full_name = "Receiver Name"
    phone = "01812345678"
    division = "Dhaka"
    district = "Dhaka"
    area = "Dhanmondi"
    address_line = "House 1, Road 2"
    postal_code = "1205"
