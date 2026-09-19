from django.contrib.auth.base_user import BaseUserManager
from django.core.exceptions import ValidationError

from apps.core.validators import normalize_bd_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, phone, full_name, password, **extra):
        user = self.model(phone=phone, full_name=full_name, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone, full_name, password=None, **extra):
        extra.setdefault("role", self.model.Role.CUSTOMER)
        return self._create(phone, full_name, password, **extra)

    def create_superuser(self, phone, full_name, password=None, **extra):
        # `User.save()` derives is_staff / is_superuser from the role.
        extra["role"] = self.model.Role.ADMIN
        return self._create(phone, full_name, password, **extra)

    def get_by_identifier(self, identifier):
        """Find a user by phone (any accepted Bangladesh format) or email. None if no match."""
        identifier = (identifier or "").strip()
        if not identifier:
            return None
        if "@" in identifier:
            return self.filter(email=identifier.lower()).first()
        try:
            phone = normalize_bd_phone(identifier)
        except ValidationError:
            return None
        return self.filter(phone=phone).first()
