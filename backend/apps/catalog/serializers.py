from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from rest_framework import serializers

from apps.core.serializers import ReplacedFilesMixin, SlugSerializerMixin

from . import services
from .models import Brand, Category, Tag

# `tree` is a real route (/categories/tree/), so no category may take that slug.
CATEGORY_RESERVED_SLUGS = frozenset({"tree"})

def slug_field():
    return serializers.CharField(
        required=False, allow_blank=True, max_length=255,
        help_text="Auto-generated from the name when omitted. Set it to override; send an empty string to switch back to automatic.",
    )


class _UniqueNameMixin:
    """Friendly, case-insensitive name uniqueness error (the DB constraint is the backstop)."""

    def validate_name(self, value):
        value = value.strip()
        queryset = self.Meta.model.objects.filter(name__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(f"A {self.Meta.model._meta.verbose_name} with this name already exists.")
        return value


# --- Public ----------------------------------------------------------------------------------


class PublicCategorySerializer(serializers.ModelSerializer):
    parent = serializers.SlugRelatedField(slug_field="slug", read_only=True, help_text="Slug of the parent category, or null")

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "image", "parent", "description", "sort_order"]
        read_only_fields = fields


@extend_schema_serializer(component_name="CategoryTreeNode")
class PublicCategoryTreeNodeSerializer(PublicCategorySerializer):
    children = serializers.SerializerMethodField()

    class Meta(PublicCategorySerializer.Meta):
        fields = [*PublicCategorySerializer.Meta.fields, "children"]
        read_only_fields = fields

    @extend_schema_field({"type": "array", "items": {"$ref": "#/components/schemas/CategoryTreeNode"}})
    def get_children(self, obj):  # documentation only: the view builds the tree itself
        return []


class CategoryLinkSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()


class PublicCategoryDetailSerializer(PublicCategorySerializer):
    breadcrumb = serializers.SerializerMethodField(help_text="Root-to-this-category path, including this category")
    children = serializers.SerializerMethodField(help_text="Visible direct sub-categories")

    class Meta(PublicCategorySerializer.Meta):
        fields = [*PublicCategorySerializer.Meta.fields, "seo_title", "seo_description", "breadcrumb", "children"]
        read_only_fields = fields

    @extend_schema_field(CategoryLinkSerializer(many=True))
    def get_breadcrumb(self, obj):
        return self.context["index"].breadcrumb(obj.pk)

    @extend_schema_field(CategoryLinkSerializer(many=True))
    def get_children(self, obj):
        return self.context["index"].children(obj.pk)


class PublicBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "logo", "description"]
        read_only_fields = fields


class PublicTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]
        read_only_fields = fields


# --- Admin -----------------------------------------------------------------------------------


class AdminCategorySerializer(SlugSerializerMixin, ReplacedFilesMixin, serializers.ModelSerializer):
    slug = slug_field()
    slug_reserved = CATEGORY_RESERVED_SLUGS
    file_fields = ("image",)
    # Annotated by the view's queryset (`Count(..., distinct=True)`), not a per-row query.
    children_count = serializers.IntegerField(read_only=True, default=0)
    products_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = [
            "id", "name", "slug", "image", "parent", "description", "is_active", "sort_order",
            "seo_title", "seo_description", "children_count", "products_count", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "children_count", "products_count", "created_at", "updated_at"]
        # the model's UniqueConstraints are checked by `validate` with friendlier messages
        validators = []

    def validate_name(self, value):
        return value.strip()

    def validate_parent(self, parent):
        try:
            services.assert_valid_parent(self.instance, parent)
        except DjangoValidationError as exc:
            # DRF already files a field-level error under "parent"; unwrap ours to avoid {"parent": {"parent": ...}}
            raise serializers.ValidationError(exc.message_dict["parent"]) from None
        return parent

    def validate(self, attrs):
        instance = self.instance
        name = attrs.get("name", instance.name if instance else None)
        parent = attrs["parent"] if "parent" in attrs else (instance.parent if instance else None)
        if instance is None or "name" in attrs or "parent" in attrs:
            clash = Category.objects.filter(parent=parent, name__iexact=name)
            if instance is not None:
                clash = clash.exclude(pk=instance.pk)
            if clash.exists():
                raise serializers.ValidationError({"name": ["A category with this name already exists under the same parent."]})
        return super().validate(attrs)

    def update(self, instance, validated_data):
        with transaction.atomic():
            if "parent" in validated_data and validated_data["parent"] != instance.parent:
                # re-check under a table lock: the earlier check may be stale by now
                services.assert_valid_parent(instance, validated_data["parent"], lock=True)
            return super().update(instance, validated_data)


@extend_schema_serializer(component_name="AdminCategoryTreeNode")
class AdminCategoryTreeNodeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "image", "parent", "is_active", "sort_order", "children"]
        read_only_fields = fields

    @extend_schema_field({"type": "array", "items": {"$ref": "#/components/schemas/AdminCategoryTreeNode"}})
    def get_children(self, obj):  # documentation only
        return []


class AdminBrandSerializer(SlugSerializerMixin, ReplacedFilesMixin, _UniqueNameMixin, serializers.ModelSerializer):
    slug = slug_field()
    file_fields = ("logo",)

    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "logo", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        validators = []


class AdminTagSerializer(SlugSerializerMixin, _UniqueNameMixin, serializers.ModelSerializer):
    slug = slug_field()

    class Meta:
        model = Tag
        fields = ["id", "name", "slug", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        validators = []
