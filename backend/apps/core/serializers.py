"""Shared serializers, mostly used to document responses in OpenAPI."""

from django.db import IntegrityError, transaction
from rest_framework import serializers

from .utils import discard_path, resolve_slug


class ErrorDetailSerializer(serializers.Serializer):
    status = serializers.IntegerField(help_text="HTTP status code.")
    code = serializers.CharField(help_text="Stable machine-readable error code.")
    message = serializers.CharField(help_text="Human-readable summary.")
    details = serializers.JSONField(
        allow_null=True,
        help_text="Field errors (validation), `{retry_after}` (throttling) or null.",
    )


class ErrorResponseSerializer(serializers.Serializer):
    """The envelope returned by every error response."""

    error = ErrorDetailSerializer()


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    service = serializers.CharField()
    version = serializers.CharField()
    time = serializers.DateTimeField()
    checks = serializers.DictField(
        child=serializers.CharField(), help_text="Per-dependency result: `ok` or `error`."
    )


class SlugSerializerMixin:
    """
    Slug handling for admin serializers of `SlugModel`s (Category, Brand, Tag, later Product...).

        class BrandSerializer(SlugSerializerMixin, serializers.ModelSerializer):
            slug = serializers.CharField(required=False, allow_blank=True, max_length=255)

    Sets `slug` / `slug_is_custom` in `validate()` following `resolve_slug`, and turns a lost
    race on the unique constraint into a 400 instead of a 500. Set `slug_reserved` for slugs that
    would collide with a route, and `slug_source` if the slug derives from a field other than `name`.
    """

    slug_source = "name"
    slug_reserved = ()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        instance = self.instance
        source = self.slug_source
        provided = "slug" in attrs
        slug_input = attrs.pop("slug", None)
        name = attrs.get(source, getattr(instance, source, None))
        name_changed = instance is not None and source in attrs and attrs[source] != getattr(instance, source)
        attrs["slug"], attrs["slug_is_custom"] = resolve_slug(
            self.Meta.model,
            name=name,
            slug=slug_input if provided else None,
            instance=instance,
            name_changed=name_changed,
            reserved=self.slug_reserved,
        )
        return attrs

    def _save_or_conflict(self, save):
        try:
            with transaction.atomic():
                return save()
        except IntegrityError:
            raise serializers.ValidationError(
                {"non_field_errors": ["Could not save: a record with the same name or slug already exists."]}
            ) from None

    def create(self, validated_data):
        return self._save_or_conflict(lambda: super(SlugSerializerMixin, self).create(validated_data))

    def update(self, instance, validated_data):
        return self._save_or_conflict(lambda: super(SlugSerializerMixin, self).update(instance, validated_data))


class ReplacedFilesMixin:
    """Deletes an image file from storage after it has been replaced or cleared by an update."""

    file_fields = ("image",)

    def update(self, instance, validated_data):
        old = {name: getattr(instance, name) for name in self.file_fields if name in validated_data}
        old = {name: (f.storage, f.name) for name, f in old.items() if f and f.name}
        instance = super().update(instance, validated_data)
        for name, (storage, path) in old.items():
            current = getattr(instance, name)
            if not current or current.name != path:
                discard_path(storage, path)
        return instance
