from rest_framework import serializers

from apps.catalog.models import Category
from apps.catalog.serializers import PublicBrandSerializer, PublicCategorySerializer
from apps.catalog.serializers_product import PublicProductListSerializer

from . import services
from .models import FLAG_SOURCES, Announcement, Faq, HomepageCategorySection, NewsletterSubscriber, Page, SectionSource

# --- public --------------------------------------------------------------------------------------------------------------


class PublicPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ["title", "slug", "content", "meta_title", "meta_description", "updated_at"]
        read_only_fields = fields


class PublicFaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faq
        fields = ["id", "category", "question", "answer"]
        read_only_fields = fields


class PublicAnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["id", "text", "link_url"]
        read_only_fields = fields


class SubscribeInputSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    source = serializers.CharField(max_length=30, required=False, allow_blank=True)


class UnsubscribeInputSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=64)


class SearchResultSerializer(serializers.Serializer):
    query = serializers.CharField()
    products = PublicProductListSerializer(many=True)
    product_count = serializers.IntegerField(help_text="All matching products; `products` holds the first `limit`.")
    categories = PublicCategorySerializer(many=True)
    brands = PublicBrandSerializer(many=True)
    suggestions = serializers.ListField(child=serializers.CharField(), help_text="Distinct names for autocomplete.")


# --- admin ---------------------------------------------------------------------------------------------------------------


class AdminPageSerializer(serializers.ModelSerializer):
    updated_by = serializers.CharField(source="updated_by.full_name", read_only=True, default=None)
    is_standard = serializers.SerializerMethodField()

    class Meta:
        model = Page
        fields = [
            "id", "title", "slug", "content", "meta_title", "meta_description", "is_active", "is_standard",
            "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_standard", "updated_by", "created_at", "updated_at"]

    def get_is_standard(self, obj) -> bool:
        return obj.slug in services.STANDARD_PAGES

    def validate_slug(self, value):
        # Standard pages keep their slug: the storefront route (/about, /terms…) is looked up by it.
        if self.instance and self.instance.slug in services.STANDARD_PAGES and value != self.instance.slug:
            raise serializers.ValidationError("A standard page's slug can't be changed.", code="locked")
        return value


class AdminFaqSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faq
        fields = ["id", "category", "question", "answer", "sort_order", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_category(self, value):
        return " ".join(value.split())


class AdminSubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsletterSubscriber
        fields = ["id", "email", "phone", "is_subscribed", "source", "created_at", "unsubscribed_at"]
        read_only_fields = ["id", "email", "phone", "source", "created_at", "unsubscribed_at"]


class AdminAnnouncementSerializer(serializers.ModelSerializer):
    is_live = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ["id", "text", "link_url", "starts_at", "ends_at", "sort_order", "is_active", "is_live", "created_at", "updated_at"]
        read_only_fields = ["id", "is_live", "created_at", "updated_at"]

    def get_is_live(self, obj) -> bool:
        return services.live_announcements().filter(pk=obj.pk).exists()

    def validate_link_url(self, value):
        try:
            return services.clean_link(value)
        except Exception as exc:  # noqa: BLE001 - surface the Django ValidationError's message on this field
            raise serializers.ValidationError(exc.message_dict["link_url"][0], code="invalid") from None

    def validate(self, attrs):
        starts = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({"ends_at": serializers.ErrorDetail("End must be after the start.", code="invalid")})
        return attrs


class SectionCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    is_active = serializers.BooleanField()


class AdminHomepageCategorySectionSerializer(serializers.ModelSerializer):
    """
    Admin: a homepage product section. `source` category needs `category_id` (title = the category's name); a flag source
    (featured / new_arrival / bestseller) uses `title`, defaulting to "Trending Products" / "New Arrivals" / "Bestsellers".
    """

    category_id = serializers.PrimaryKeyRelatedField(source="category", queryset=Category.objects.all(), allow_null=True, required=False)
    category = SectionCategorySerializer(read_only=True, allow_null=True)
    position_label = serializers.CharField(source="get_position_display", read_only=True)
    source_label = serializers.CharField(source="get_source_display", read_only=True)
    display_title = serializers.CharField(read_only=True)

    class Meta:
        model = HomepageCategorySection
        fields = ["id", "source", "source_label", "category_id", "category", "title", "display_title", "position", "position_label",
                  "sort_order", "product_limit", "rows", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "source_label", "category", "display_title", "position_label", "created_at", "updated_at"]

    def validate(self, attrs):
        source = attrs.get("source", getattr(self.instance, "source", SectionSource.CATEGORY))
        if source == SectionSource.CATEGORY:
            if attrs.get("category", getattr(self.instance, "category", None)) is None:
                raise serializers.ValidationError({"category_id": "Choose a category."})
            attrs["title"] = ""  # a category section is always titled with the category's name
        else:
            attrs["category"] = None
            title = " ".join(attrs.get("title", getattr(self.instance, "title", "") or "").split())
            attrs["title"] = title or FLAG_SOURCES[source][1]
        return attrs


class PublicHomepageCategorySectionSerializer(serializers.ModelSerializer):
    category = SectionCategorySerializer(read_only=True, allow_null=True)
    title = serializers.CharField(source="display_title", read_only=True)
    filter = serializers.DictField(source="product_filter", child=serializers.CharField(), read_only=True,
                                   help_text="Query filters for GET /products/ that give this section's products.")

    class Meta:
        model = HomepageCategorySection
        fields = ["id", "source", "title", "filter", "category", "position", "sort_order", "product_limit", "rows"]
        read_only_fields = fields
