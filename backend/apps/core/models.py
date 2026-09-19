"""
Abstract base models shared by every app.

    class Product(TimeStampedModel, SoftDeleteModel): ...
"""

from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Adds `created_at` / `updated_at`."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def _touch_fields(self, **fields):
        # QuerySet.update() bypasses auto_now, so keep `updated_at` fresh by hand.
        if any(f.name == "updated_at" for f in self.model._meta.get_fields()):
            fields["updated_at"] = timezone.now()
        return fields

    def delete(self):
        """Soft delete: flag the rows instead of removing them. Returns the row count."""
        return self.update(**self._touch_fields(is_deleted=True, deleted_at=timezone.now()))

    def hard_delete(self):
        """Really remove the rows from the database."""
        return super().delete()

    def restore(self):
        return self.update(**self._touch_fields(is_deleted=False, deleted_at=None))

    def alive(self):
        return self.filter(is_deleted=False)

    def dead(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager: hides soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    """
    Soft deletion for products, categories and orders.

    * `Model.objects`      -> only live rows (safe default for every query)
    * `Model.all_objects`  -> live and deleted rows (admin restore views, reports)
    * `instance.delete()` / `queryset.delete()` -> soft delete
    * `instance.hard_delete()` / `queryset.hard_delete()` -> real DELETE

    Things to know:
    * Forward foreign-key access (`order_item.product`) still resolves a
      soft-deleted target, because Django uses the plain base manager for that.
    * `objects` is the default manager, so DRF's `UniqueValidator` will not see
      soft-deleted rows. Slugs/SKUs stay unique at the database level, so use
      `apps.core.utils.unique_slugify` (which checks all rows) when generating slugs.
    """

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        abstract = True

    def _touch_field_names(self):
        names = ["is_deleted", "deleted_at"]
        if any(f.name == "updated_at" for f in self._meta.get_fields()):
            names.append("updated_at")
        return names

    def delete(self, using=None, keep_parents=False):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=self._touch_field_names(), using=using)

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=self._touch_field_names())

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)
