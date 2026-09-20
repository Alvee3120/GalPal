from django.core.exceptions import ValidationError
from django.db import models

from apps.catalog.models import Product
from apps.core.models import TimeStampedModel
from apps.core.utils import UploadPath
from apps.core.validators import validate_http_url, validate_image_file, validate_video_file


class VideoCard(TimeStampedModel):
    """
    A homepage video card: either an uploaded file or an external link (e.g. YouTube), never
    both. Multiple products can be tagged on one video, shown as shoppable product cards
    alongside it (see `apps.catalog.serializers_product.ProductPickerSerializer` for the admin's
    search-as-you-type product picker used to build this list).
    """

    title = models.CharField(max_length=120)
    video_file = models.FileField(upload_to=UploadPath("videos"), validators=[validate_video_file], blank=True)
    external_url = models.URLField(max_length=500, blank=True, validators=[validate_http_url])
    thumbnail = models.ImageField(upload_to=UploadPath("videos"), validators=[validate_image_file])

    products = models.ManyToManyField(Product, related_name="videos", blank=True)

    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]
        constraints = [
            models.CheckConstraint(
                # Exactly one of video_file / external_url: neither blank-blank nor set-set.
                condition=(
                    (models.Q(video_file="") & ~models.Q(external_url=""))
                    | (~models.Q(video_file="") & models.Q(external_url=""))
                ),
                name="video_card_exactly_one_source",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        # The CheckConstraint above is the DB-level backstop (belt-and-braces against a direct ORM
        # write); the API's real validation, with a friendly message, lives in the serializer.
        if bool(self.video_file) == bool(self.external_url):
            raise ValidationError(
                "Provide exactly one of an uploaded video or an external URL, not both or neither.",
                code="video_source_required",
            )

    @property
    def video_url(self):
        """The URL to play: the uploaded file if there is one, else the external link."""
        return self.video_file.url if self.video_file else self.external_url
