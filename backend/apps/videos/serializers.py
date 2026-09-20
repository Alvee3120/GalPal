from rest_framework import serializers

from apps.catalog.models import Product
from apps.catalog.serializers_product import ProductPickerSerializer
from apps.core.serializers import ReplacedFilesMixin

from . import services
from .models import VideoCard


class AbsoluteVideoUrlMixin:
    """
    `video_url` as a real, absolute URL: `obj.video_url` (the model property) is storage-relative
    for an uploaded file (external_url is already absolute). `build_absolute_uri()` is what
    ImageField/FileField do automatically, but `video_url` is a plain string, so it's done by hand.
    Shared by the public and admin serializers so this only needs fixing in one place.
    """

    def get_video_url(self, obj) -> str:
        if not obj.video_file:
            return obj.video_url
        request = self.context.get("request")
        return request.build_absolute_uri(obj.video_url) if request else obj.video_url


# --- public ----------------------------------------------------------------------------------


class ProductCardSerializer(serializers.ModelSerializer):
    """A shoppable product card, as shown alongside a public video."""

    image = serializers.ImageField(source="feature_image", read_only=True)
    price = serializers.DecimalField(source="effective_price", max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "image", "price"]
        read_only_fields = fields


class PublicVideoCardSerializer(AbsoluteVideoUrlMixin, serializers.ModelSerializer):
    video_url = serializers.SerializerMethodField()
    products = ProductCardSerializer(many=True, read_only=True)

    class Meta:
        model = VideoCard
        fields = ["id", "title", "video_url", "thumbnail", "products"]
        read_only_fields = fields


# --- admin -----------------------------------------------------------------------------------


class AdminVideoCardSerializer(AbsoluteVideoUrlMixin, ReplacedFilesMixin, serializers.ModelSerializer):
    file_fields = ("video_file", "thumbnail")
    product_ids = serializers.PrimaryKeyRelatedField(
        source="products", queryset=Product.objects.all(), many=True, required=False, write_only=True
    )
    products = ProductPickerSerializer(many=True, read_only=True)
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = VideoCard
        fields = [
            "id", "title", "video_file", "external_url", "video_url", "thumbnail",
            "product_ids", "products", "sort_order", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "video_url", "created_at", "updated_at"]

    def validate(self, attrs):
        video_file = attrs.get("video_file", self.instance.video_file if self.instance else None)
        external_url = attrs.get("external_url", self.instance.external_url if self.instance else "")
        if bool(video_file) == bool(external_url):
            raise serializers.ValidationError(
                "Provide exactly one of an uploaded video or an external URL, not both or neither."
            )
        return attrs

    def create(self, validated_data):
        products = validated_data.pop("products", [])
        video = VideoCard.objects.create(**validated_data)
        video.products.set(products)
        return video

    def update(self, instance, validated_data):
        products = validated_data.pop("products", None)
        instance = super().update(instance, validated_data)
        if products is not None:
            instance.products.set(products)
        return instance
