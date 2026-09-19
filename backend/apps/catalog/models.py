from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import SlugModel, TimeStampedModel
from apps.core.utils import UploadPath
from apps.core.validators import validate_image_file


def _image(folder):
    return models.ImageField(upload_to=UploadPath(folder), validators=[validate_image_file], null=True, blank=True)


class Category(TimeStampedModel, SlugModel):
    """
    A product category. Categories nest without a depth limit via `parent`.

    A category is publicly visible only if it AND all of its ancestors are active
    (see `services.CategoryIndex`). Use `services` to move/delete categories: they keep the
    tree free of cycles and refuse to orphan products.
    """

    name = models.CharField(max_length=120)
    image = _image("categories")
    # PROTECT: the database refuses to delete a category that still has children. The
    # service layer offers "re-parent the children" or "block" instead of cascading.
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    seo_title = models.CharField(max_length=70, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"
        indexes = [models.Index(fields=["parent", "sort_order"])]
        constraints = [
            models.CheckConstraint(condition=~Q(parent=models.F("id")), name="category_not_own_parent"),
            # Sibling names are unique, ignoring case. Two constraints because NULL parents
            # (top-level categories) are never equal to each other in a unique index.
            models.UniqueConstraint(
                Lower("name"), "parent", name="category_unique_name_per_parent"
            ),
            models.UniqueConstraint(
                Lower("name"), condition=Q(parent__isnull=True), name="category_unique_name_top_level"
            ),
        ]

    def __str__(self):
        return self.name

    def product_count(self):
        """
        Number of products in this category.

        Module 4's `Product.categories` M2M must use `related_name="products"`; until then there
        is no such relation and this is 0. `services.delete_category` relies on it.
        """
        products = getattr(self, "products", None)
        return products.count() if products is not None else 0


class Brand(TimeStampedModel, SlugModel):
    name = models.CharField(max_length=120)
    logo = _image("brands")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="brand_unique_name")]

    def __str__(self):
        return self.name


class Tag(TimeStampedModel, SlugModel):
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="tag_unique_name")]

    def __str__(self):
        return self.name
