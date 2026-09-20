from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.core.utils import UploadPath
from apps.core.validators import validate_http_url, validate_image_file

_min_zero = MinValueValidator(0)
_delay_range = [MinValueValidator(1), MaxValueValidator(120)]


class LinkTarget(models.TextChoices):
    SELF = "_self", "Same tab"
    BLANK = "_blank", "New tab"


class HeroSliderConfig(TimeStampedModel):
    """
    The one and only row of slider-wide settings (always `id=1`), read through
    `services.get_slider_config()` (cached, same pattern as Module 2's SiteSettings).

    A banner's own `slide_delay_override` wins over `slide_delay_seconds` here when set.
    """

    slide_delay_seconds = models.PositiveIntegerField(default=5, validators=_delay_range)
    autoplay = models.BooleanField(default=True)
    loop = models.BooleanField(default=True)

    class Meta:
        verbose_name = "hero slider config"
        verbose_name_plural = "hero slider config"
        constraints = [models.CheckConstraint(condition=Q(id=1), name="hero_slider_config_single_row")]

    def __str__(self):
        return "Hero slider config"

    def save(self, *args, **kwargs):
        self.pk = self.id = 1
        kwargs.pop("force_insert", None)  # `create()` on the singleton behaves as an upsert
        if self._state.adding:
            existing = type(self).objects.filter(pk=1).values_list("created_at", flat=True).first()
            if existing:
                self.created_at = existing
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError

        raise ValidationError("The hero slider config row cannot be deleted.", code="protected")


class HeroBanner(TimeStampedModel):
    """
    One slide of the homepage hero slider.

    `title` is internal only (never returned publicly). Falls back to the desktop image for
    devices without their own image set — see `effective_tablet_image`/`effective_mobile_image`.
    Visible publicly only while `is_active` and within `[start_at, end_at]` (either may be blank).
    """

    title = models.CharField(max_length=120, help_text="Internal label, not shown to customers.")
    desktop_image = models.ImageField(upload_to=UploadPath("banners"), validators=[validate_image_file])
    tablet_image = models.ImageField(
        upload_to=UploadPath("banners"), validators=[validate_image_file], null=True, blank=True,
        help_text="Falls back to the desktop image when blank.",
    )
    mobile_image = models.ImageField(
        upload_to=UploadPath("banners"), validators=[validate_image_file], null=True, blank=True,
        help_text="Falls back to the desktop image when blank.",
    )
    alt_text = models.CharField(max_length=150, blank=True)

    link_url = models.URLField(max_length=500, blank=True, validators=[validate_http_url])
    link_target = models.CharField(max_length=7, choices=LinkTarget.choices, default=LinkTarget.SELF)
    button_text = models.CharField(max_length=40, blank=True)

    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    start_at = models.DateTimeField(null=True, blank=True, help_text="Blank: visible immediately.")
    end_at = models.DateTimeField(null=True, blank=True, help_text="Blank: never expires.")
    slide_delay_override = models.PositiveIntegerField(
        null=True, blank=True, validators=_delay_range, help_text="Seconds. Blank uses the slider-wide default."
    )

    class Meta:
        ordering = ["sort_order", "-created_at"]
        indexes = [models.Index(fields=["is_active", "sort_order"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__isnull=True) | Q(start_at__isnull=True) | Q(end_at__gt=models.F("start_at")),
                name="hero_banner_end_after_start",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def effective_tablet_image(self):
        return self.tablet_image if self.tablet_image else self.desktop_image

    @property
    def effective_mobile_image(self):
        return self.mobile_image if self.mobile_image else self.desktop_image
