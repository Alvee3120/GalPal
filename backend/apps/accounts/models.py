from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.utils import UploadPath
from apps.core.validators import normalize_bd_phone, validate_bd_phone, validate_image_file

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CCE = "cce", "Customer Care Executive"
        CUSTOMER = "customer", "Customer"

    # The phone number is the primary login identifier; email is optional.
    phone = models.CharField(
        max_length=11, unique=True, validators=[validate_bd_phone],
        help_text="Bangladesh mobile in local format, e.g. 01712345678.",
    )
    email = models.EmailField(unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CUSTOMER, db_index=True)
    avatar = models.ImageField(
        upload_to=UploadPath("avatars"), validators=[validate_image_file], null=True, blank=True
    )

    is_active = models.BooleanField(default=True, db_index=True)
    # Derived from `role` in save(); only Admin-role users may enter the Django admin fallback.
    is_staff = models.BooleanField(default=False, editable=False)

    # Accounts created for a guest at checkout get a generated password they must replace.
    created_via_checkout = models.BooleanField(default=False, db_index=True)
    must_change_password = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"

    def save(self, *args, **kwargs):
        self.phone = normalize_bd_phone(self.phone)
        self.email = (self.email or "").strip().lower() or None  # "" would break uniqueness
        # Role is the single source of truth for Django-admin access.
        self.is_staff = self.is_superuser = self.role == self.Role.ADMIN
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = {*update_fields, "phone", "email", "is_staff", "is_superuser"}
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(" ")[0]

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_cce(self):
        return self.role == self.Role.CCE

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER


class Address(TimeStampedModel):
    """A saved delivery address in a user's address book."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=50, blank=True, help_text="e.g. Home, Office")
    full_name = models.CharField(max_length=150, help_text="Recipient name")
    phone = models.CharField(max_length=11, validators=[validate_bd_phone], help_text="Recipient phone")
    division = models.CharField(max_length=60, blank=True)
    district = models.CharField(max_length=60)
    area = models.CharField(max_length=100, blank=True, help_text="Thana / upazila / area")
    address_line = models.CharField(max_length=255)
    postal_code = models.CharField(max_length=10, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name_plural = "addresses"
        constraints = [
            # At most one default address per user, enforced by the database.
            models.UniqueConstraint(
                fields=["user"], condition=Q(is_default=True), name="unique_default_address_per_user"
            ),
        ]
        indexes = [models.Index(fields=["district"])]

    def __str__(self):
        return f"{self.label or 'Address'} – {self.full_name}, {self.district}"

    def save(self, *args, **kwargs):
        self.phone = normalize_bd_phone(self.phone)
        super().save(*args, **kwargs)


class PasswordResetOTP(TimeStampedModel):
    """A one-time code for the forgot-password flow. Only a keyed hash of the code is stored."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_otps")
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"OTP for user {self.user_id}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at
