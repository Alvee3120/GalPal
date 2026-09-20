from rest_framework import serializers

from apps.core.serializers import ReplacedFilesMixin

from . import services
from .models import HeroBanner, HeroSliderConfig

# --- public ----------------------------------------------------------------------------------


class PublicSliderConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroSliderConfig
        fields = ["slide_delay_seconds", "autoplay", "loop"]
        read_only_fields = fields


class PublicHeroBannerSerializer(serializers.ModelSerializer):
    desktop_image = serializers.ImageField(read_only=True)
    tablet_image = serializers.ImageField(source="effective_tablet_image", read_only=True)
    mobile_image = serializers.ImageField(source="effective_mobile_image", read_only=True)

    class Meta:
        model = HeroBanner
        fields = [
            "id", "desktop_image", "tablet_image", "mobile_image", "alt_text",
            "link_url", "link_target", "button_text", "slide_delay_override",
        ]
        read_only_fields = fields


class HeroSliderSerializer(serializers.Serializer):
    """`GET /hero-banners/` response shape: slider-wide config plus the banners to show."""

    config = PublicSliderConfigSerializer()
    banners = PublicHeroBannerSerializer(many=True)


# --- admin -----------------------------------------------------------------------------------


class AdminSliderConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroSliderConfig
        fields = ["slide_delay_seconds", "autoplay", "loop", "updated_at"]
        read_only_fields = ["updated_at"]


class AdminHeroBannerSerializer(ReplacedFilesMixin, serializers.ModelSerializer):
    file_fields = ("desktop_image", "tablet_image", "mobile_image")
    is_currently_visible = serializers.SerializerMethodField()

    class Meta:
        model = HeroBanner
        fields = [
            "id", "title", "desktop_image", "tablet_image", "mobile_image", "alt_text",
            "link_url", "link_target", "button_text", "sort_order", "is_active",
            "start_at", "end_at", "slide_delay_override", "is_currently_visible",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_currently_visible", "created_at", "updated_at"]

    def get_is_currently_visible(self, obj) -> bool:
        return services.visible_banners().filter(pk=obj.pk).exists()

    def validate(self, attrs):
        start = attrs.get("start_at", self.instance.start_at if self.instance else None)
        end = attrs.get("end_at", self.instance.end_at if self.instance else None)
        if start and end and end <= start:
            raise serializers.ValidationError({"end_at": ["Must be after the start date."]})
        return attrs
